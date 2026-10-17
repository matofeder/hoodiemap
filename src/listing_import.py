"""Import one public nehnutelnosti.sk listing into a demo presentation.

Only for building a demo for the agent who owns the listing: one page fetched on request, never crawled.
The detail page carries schema.org JSON-LD (title, description, price, photos, agency) and the Next.js
flight data of the listing (exact address, parameters, 3D tour), which is where most fields come from.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit

import httpx

from osm import USER_AGENT

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = {"www.nehnutelnosti.sk", "nehnutelnosti.sk"}
MAX_PHOTOS = 20
TIMEOUT_S = 20

PROPERTY_TYPES = {"APARTMENTS": "flat", "HOUSES": "house", "LANDS": "land", "PLOTS": "land"}
CONDITIONS = {
    "novostavba": "new", "kompletná rekonštrukcia": "renovated", "čiastočná rekonštrukcia": "partly_renovated",
    "pôvodný stav": "original", "vo výstavbe": "under_construction", "developerský projekt": "under_construction",
}
ENERGY = {"A0", "A1", "A", "B", "C", "D", "E", "F", "G"}
ROOMS_BY_CATEGORY = {"ONE_ROOM": 1, "TWO_ROOM": 2, "THREE_ROOM": 3, "FOUR_ROOM": 4, "FIVE_PLUS_ROOM": 5}
# attribute label (lowercase, substring) -> feature
FEATURE_LABELS = {"balkón": "balcony", "lodži": "loggia", "lódži": "loggia", "teras": "terrace", "pivnic": "cellar",
                  "garáž": "garage", "parkovan": "parking", "záhrad": "garden"}


class ImportError_(RuntimeError):  # noqa: N801 (ImportError is a builtin)
    """The URL is not an importable listing, or the page could not be read."""


@dataclass
class ImportedListing:
    source_url: str
    data: dict                      # PresentationData fields except photos; location may lack lat/lon
    address_query: str | None       # what to geocode for exact coordinates
    point: tuple[float, float] | None  # the portal's own point (approximate, radius ~200 m)
    photo_urls: list[str] = field(default_factory=list)
    agency: str | None = None
    warnings: list[str] = field(default_factory=list)


def check_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS or not parts.path.startswith("/detail/"):
        raise ImportError_("Use the https://www.nehnutelnosti.sk/detail/… link of one listing.")
    return f"https://www.nehnutelnosti.sk{parts.path}"


def fetch(url: str, transport: httpx.BaseTransport | None = None) -> str:
    try:
        with httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                          transport=transport) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPError as exc:
        raise ImportError_(f"The listing page could not be loaded ({exc.__class__.__name__}).") from exc


def fetch_photo(url: str, transport: httpx.BaseTransport | None = None) -> bytes:
    with httpx.Client(timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, transport=transport) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


# --- page parsing ---------------------------------------------------------------------------

def _json_ld_nodes(html: str) -> list[dict]:
    nodes = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            block = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for node in block.get("@graph", [block]) if isinstance(block, dict) else block:
            if isinstance(node, dict):
                nodes.append(node)
    return nodes


def _flight_text(html: str) -> str:
    """Concatenated Next.js flight chunks: self.__next_f.push([1,"…"])."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    out = []
    for c in chunks:
        try:
            out.append(json.loads(f'"{c}"'))
        except json.JSONDecodeError:
            continue
    return "".join(out)


def _advertisement(flight: str) -> dict | None:
    m = re.search(r'"advertisement":\s*(\{)\s*"id":', flight)
    if not m:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(flight, m.start(1))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _flight_ref(flight: str, ref) -> str | None:
    """Resolve a "$2e" reference to a text row `2e:T<hex byte length>,<text>`."""
    if not isinstance(ref, str) or not ref.startswith("$"):
        return ref if isinstance(ref, str) else None
    m = re.search(rf'(?:^|\n){re.escape(ref[1:])}:T([0-9a-f]+),', flight)
    if not m:
        return None
    raw = flight.encode("utf-8")
    start = len(flight[:m.end()].encode("utf-8"))
    return raw[start:start + int(m.group(1), 16)].decode("utf-8", errors="replace")


def _number(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = re.sub(r"[^\d,.-]", "", value).replace(",", ".")
        try:
            return float(s) if s else None
        except ValueError:
            return None
    return None


def _clean_description(text: str | None) -> str | None:
    if not text:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:10_000] or None


def parse(html: str, source_url: str) -> ImportedListing:
    nodes = _json_ld_nodes(html)
    by_type = {}
    for n in nodes:
        by_type.setdefault(n.get("@type"), n)
    product, offer = by_type.get("Product", {}), by_type.get("Offer", {})
    flight = _flight_text(html)
    ad = _advertisement(flight) or {}
    if not product and not ad:
        raise ImportError_("This page does not look like a listing (no listing data found).")

    p = ad.get("parameters") or {}
    attrs = {str(a.get("label", "")).lower(): str(a.get("value", "")) for a in p.get("attributes") or []
             if isinstance(a, dict)}
    warnings = []

    category = p.get("category") or {}
    rooms = _number(attrs.get("počet izieb / miestností"))
    if rooms is None:
        sub = str(category.get("subValue", ""))
        rooms = next((n for k, n in ROOMS_BY_CATEGORY.items() if sub.startswith(k)), None)

    # The portal counts storeys from 1 (ground floor = 1): "3 of 4" is the 2nd floor of a 3-floor block.
    floor = p.get("floor")
    floors_total = p.get("numberOfFloors")
    if isinstance(floor, int):
        floor -= 1
        warnings.append("Poschodie je prepočítané z portálu (podlažie − 1). Skontrolujte ho.")
    if isinstance(floors_total, int):
        floors_total = max(1, floors_total - 1)

    features = []
    if p.get("hasElevator"):
        features.append("elevator")
    for label, value in attrs.items():
        for needle, feature in FEATURE_LABELS.items():
            if needle in label and value.strip().lower() not in ("nie", "0", ""):
                features.append(feature)
    if "výťah" in attrs.get("vybavenie", "").lower():
        features.append("elevator")

    price = (p.get("price") or {}).get("priceNum")
    if price is None:
        price = _number((offer.get("priceSpecification") or {}).get("price"))
    transaction = str(p.get("transaction") or "").lower()
    business = str((offer.get("businessFunction") or {}).get("@id", ""))
    offer_kind = "rent" if "prenáj" in transaction or "LeaseOut" in business else "sale"

    energy = str(p.get("energyRatingCertificate") or "").upper()
    condition = CONDITIONS.get(str(p.get("realEstateState") or "").strip().lower())
    area = _number(p.get("area"))
    if area is None:
        area = _number((by_type.get("Accommodation", {}).get("floorSize") or {}).get("value"))
    land = _number(attrs.get("plocha pozemku"))

    year = p.get("yearOfConstruction") if isinstance(p.get("yearOfConstruction"), int) else None
    if year is not None and not 1000 <= year <= date.today().year + 5:
        warnings.append(f"Rok výstavby z portálu ({year}) nevyzerá správne, vynechali sme ho.")
        year = None

    loc = ad.get("location") or {}
    street = " ".join(x for x in [loc.get("street"), loc.get("streetNumber")] if x)
    city = loc.get("city")
    label = ", ".join(x for x in [street, city] if x) or (loc.get("name") or "").split(", okres")[0] or None
    tier = "address" if loc.get("streetNumber") else "street" if loc.get("street") else "city"
    point = loc.get("point") or {}
    lat, lon = _number(point.get("latitude")), _number(point.get("longitude"))
    if tier != "address":
        warnings.append("Inzerát neuvádza číslo domu, mapa ukazuje celú ulicu alebo obec.")

    photos = [ph.get("largeUrl") or ph.get("origUrl") for ph in (ad.get("media") or {}).get("photos") or []]
    if not photos:
        photos = [img.get("url") for img in product.get("image") or [] if isinstance(img, dict)]
    photos = [u for u in photos if isinstance(u, str) and u.startswith("https://")][:MAX_PHOTOS]

    tours = (ad.get("media") or {}).get("inspections3d") or []
    tour_url = next((t.get("url") for t in tours if isinstance(t, dict) and str(t.get("url", "")).startswith("https://")), None)

    advertiser = ad.get("advertiser") or {}
    agency = (advertiser.get("agency") or {}).get("name") or (by_type.get("RealEstateAgent") or {}).get("name")
    description = _clean_description(_flight_ref(flight, ad.get("description")) or product.get("description"))

    data = {
        "location": {"lat": lat, "lon": lon, "tier": tier, "name": loc.get("street") if tier == "street" else None,
                     "label": label},
        "title": (ad.get("title") or product.get("name") or "").strip()[:200] or None,
        "offer": offer_kind,
        "price_eur": price,
        "params": {
            "property_type": PROPERTY_TYPES.get(str(category.get("mainValue", ""))),
            "rooms": int(rooms) if rooms is not None else None,
            "area_m2": area,
            "land_m2": land,
            "floor": floor if isinstance(floor, int) else None,
            "floors_total": floors_total if isinstance(floors_total, int) else None,
            "condition": condition,
            "energy_class": energy if energy in ENERGY else None,
            "year_built": year,
            "features": list(dict.fromkeys(features)),
        },
        "description": description,
        "tour_url": tour_url,
        "agent": {"name": advertiser.get("name"), "agency": agency},
    }
    return ImportedListing(
        source_url=source_url, data=data,
        address_query=label if tier == "address" else None,
        point=(lat, lon) if lat is not None and lon is not None else None,
        photo_urls=photos, agency=agency, warnings=warnings,
    )
