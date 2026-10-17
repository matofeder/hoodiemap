# HoodieMap — Property Presentation (Phase 1a)

**Date:** 2026-10-17
**Status:** Implemented on `feat/presentation` (phase 1a + 1b)
**Builds on:** `2026-09-26-playful-iso-map-design.md`, `2026-09-26-location-search-tiers-design.md`
**Product context:** "Živá prezentácia nehnuteľnosti" product proposal (v0.1, 2026-10-17)

---

## Why

Agents describe the neighbourhood from memory ("kompletná občianska vybavenosť v okolí") and portal listings are static. HoodieMap can produce a map and exact distances for any Slovak address in seconds. Phase 1 wraps that in a shareable one-page presentation of a property, so we can build demos from real listings and show them to the first 10–20 agents.

## Goal

- An agent creates a presentation in an editor: address, title, price, parameters, description, photos, contact.
- The presentation lives on one link (`/p/{id}`): gallery, parameters, description, the 3D neighbourhood map, "Lokalita v číslach" (distances and walk times), a contact form, a QR code.
- A buyer leaves a contact through the form; the agent sees the leads in the editor.
- Demo presentations are non-public: unguessable id, `noindex`, optional expiry, a "Ukážka pre …" banner.

Success: a presentation for a real address (or the fixture) is created, opened on desktop and phone, a lead is submitted and shows up in the editor; it all survives a server restart.

## Non-goals (later phases)

- Voice updates, "Sledovať" followers and e-mail notifications (phase 2).
- Buyer assistant, 3D interior (phase 3–4).
- Accounts, billing, teams. Phase 1 uses a secret edit link instead of a login.
- Real routing times: the existing straight-line estimate (`travelTime`) stays, labelled as approximate.

---

## 1. Data

Postgres (psycopg 3 + pool, no ORM). Schema in versioned SQL files `migrations/NNNN_*.sql`, applied on first use and tracked in `schema_migrations` (advisory lock against parallel workers). `data` and `scene` are `jsonb`; edits that read-modify-write `data` run under `SELECT … FOR UPDATE`, photo append/remove are single atomic `UPDATE`s. Photos stay on disk under `{storage.dir}/photos/{presentation_id}/` (git-ignored).

### presentations

| column | type | notes |
|---|---|---|
| id | text pk | 12 url-safe random chars, the public id |
| edit_token | text | 32 url-safe random chars; required for every write |
| created_at, updated_at | text | ISO 8601 UTC |
| expires_at | text, null | after it the public page answers 410 |
| demo_for | text, null | e.g. agency name, shown as "Ukážka pre …" |
| source_url | text, null | the portal listing an imported demo came from |
| data | text (JSON) | the editable fields below |
| scene | text (JSON) | snapshot of `/api/scene` taken when the location is set |

Editable fields (`data`), all optional except `location`:

```json
{
  "location": {"lat": 48.2864, "lon": 17.2722, "tier": "address", "name": null, "label": "Záhradná 12, Pezinok"},
  "title": "3-izbový byt s balkónom",
  "offer": "sale",                    // sale | rent
  "price_eur": 189000,
  "price_note": "vrátane parkovacieho miesta",
  "params": {
    "property_type": "flat",          // flat | house | land | other
    "rooms": 3, "area_m2": 72, "land_m2": null,
    "floor": 4, "floors_total": 7,
    "condition": "renovated",         // new | renovated | partly_renovated | original | under_construction
    "energy_class": "B", "year_built": 1987,
    "features": ["balcony", "elevator", "cellar", "parking"]
  },
  "description": "…",
  "tour_url": "https://my.matterport.com/show/?m=…",   // optional 3D tour, shown as a button
  "agent": {"name": "…", "phone": "…", "email": "…", "agency": "…"},
  "photos": [{"id": "…", "w": 2000, "h": 1500, "caption": "Obývačka"}]
}
```

The photo order is the order of `photos`.

### leads

`id`, `presentation_id`, `created_at`, `name`, `email`, `phone`, `message`. A lead needs a name, an e-mail or a phone, and the consent checkbox; a filled honeypot field is accepted silently and dropped.

### Photos

Accepted: JPEG, PNG, WebP (checked by decoding, not by extension), ≤ 15 MB, ≤ 40 per presentation. Each upload is re-encoded with Pillow: EXIF orientation applied, metadata stripped, a `large` JPEG (longest side 2000 px) and a `thumb` (600 px).

## 2. API

| method | path | auth | |
|---|---|---|---|
| POST | `/api/presentations` | — | create from `data` (+ `demo_for`, `expires_in_days`, `fixture`); builds the scene snapshot; returns `{id, edit_token}` |
| GET | `/api/presentations/{id}` | — | public view: `data`, `scene`, `demo_for`, `expires_at`; 404 unknown, 410 expired |
| GET | `/api/presentations/{id}/edit` | token | same plus `leads` |
| PATCH | `/api/presentations/{id}` | token | merge-update `data` (top-level keys replace); a changed `location` rebuilds the scene |
| POST | `/api/presentations/{id}/photos` | token | multipart `file`; appends to `photos` |
| DELETE | `/api/presentations/{id}/photos/{photo_id}` | token | |
| GET | `/api/presentations/{id}/photos/{photo_id}/{size}` | — | `large` or `thumb`; long cache |
| POST | `/api/presentations/{id}/leads` | — | buyer contact form |

The token travels in the `X-Edit-Token` header. In the browser the edit link is `/upravit/{id}#{token}`: the fragment never reaches the server logs or a `Referer`.

Every presentation response carries `X-Robots-Tag: noindex, nofollow`. If the scene cannot be built (Overpass down), create and location changes answer 502 with the existing `AREA_FAILED_DETAIL` and nothing is saved.

## 3. Pages

Vite multi-page build: `presentation.html` (`/p/{id}`) and `editor.html` (`/novy`, `/upravit/{id}`). In dev a small Vite middleware rewrites these paths; in production FastAPI returns the built HTML for them.

### Presentation (`/p/{id}`)

Top to bottom, one column on phones, two on wide screens where it helps:

1. Demo banner ("Ukážka pre {demo_for} · platí do {date}") when `demo_for` is set.
2. Title, address, price (`189 000 €`, `850 €/mes.` for rent), key facts row (izby, m², poschodie, stav, energetická trieda).
3. Gallery: a large photo with thumbnails; tap opens a full-screen viewer with arrows / swipe / Esc.
4. Description (plain text, paragraphs kept).
5. Parameters list and features.
6. **Okolie:** the existing 3D map (`createStage` on the snapshot) and **Lokalita v číslach**: one row per POI category, nearest first — name or category label, distance, `travelTime`. Footnote that times are estimates from straight-line distance.
7. Contact: agent card + form (meno, e-mail, telefón, správa, súhlas). Success state replaces the form.
8. QR code to the page, OSM attribution.

### Editor (`/novy`, `/upravit/{id}`)

One form: address search (the existing `/api/geocode`), title, offer, price, parameters, description, agent, demo fields (on create). Photos: upload (multiple), reorder (move up / down), caption, delete. After saving: the public link with copy button, the QR code (download as PNG for print), and the list of leads. The edit link is shown once with a "save this link" note; it is the only key to the presentation.

## 4. Tests

- `tests/test_presentations.py`: store round-trip, token checks, expiry → 410, PATCH merge and scene rebuild, photo upload validation and re-encoding, lead validation and honeypot, noindex header.
- vitest: `localityRows(scene)`, price and parameter formatting, photo order helpers.

---

## 5. Phase 1b: voice and AI draft

Provider-neutral by design: the LLM is any OpenAI-compatible `/chat/completions` API (a cheap hosted model such as DeepSeek or Qwen), speech goes to any OpenAI-compatible `/audio/transcriptions` server (a local whisper with a Slovak model). Both are off until `ai.llm` / `ai.stt` are set in `config.yaml`; `GET /api/features` tells the editor which to show. Setup notes: `docs/ai-providers.md`.

| method | path | auth | |
|---|---|---|---|
| GET | `/api/features` | — | `{"ai": {"voice": bool, "text": bool}}` |
| POST | `/api/presentations/{id}/ai/transcribe` | token | multipart `file` (≤ 25 MB) → `{text}`; 503 off, 502 provider failed |
| POST | `/api/presentations/{id}/ai/draft` | token | `{transcript, data}` (the editor's unsaved values) → a sanitized draft + `missing`; nothing is saved |

- The prompt carries the address label, the known listing fields, the scene's POIs as "name: distance, time" lines and the transcript. It never carries the agent's or buyers' contacts, photos or coordinates. The editor warns the agent not to say the owner's name or contacts (the transcript goes to the LLM as spoken).
- Rules in the prompt: facts only from the input, unknown → null and listed in `missing`, concrete distances instead of "kompletná občianska vybavenosť", no price in the text.
- Every field of the answer is validated on its own against the listing model; a bad field becomes null instead of failing the whole draft. `<think>` blocks and code fences are stripped; a server without JSON mode is retried without `response_format`.
- The editor merges the draft into the form (fills what the draft knows, adds features, never clears), highlights the changed fields and leaves saving to the agent.
- Recording uses `MediaRecorder` (WebM/Opus, MP4 on Safari), max 10 minutes; it needs HTTPS or localhost. Without a microphone the agent can upload an audio file (e.g. a phone voice memo).

---

## 6. Demo import from nehnutelnosti.sk

The sales demo: paste one listing URL, get a non-public presentation of that listing to show its agent.

- `POST /api/import` `{url, demo_for?, expires_in_days = 30, fixture?}` with `X-Admin-Token` (= `$HOODIEMAP_ADMIN_TOKEN`; import is off without it). Admin page: `/import`.
- Only `https://www.nehnutelnosti.sk/detail/…` URLs; one page plus its photos (≤ 20) per request, never crawled. `robots.txt` allows `/detail/`.
- Parsing (`listing_import.py`): schema.org JSON-LD (Product, Offer, Accommodation, RealEstateAgent) and the listing object in the Next.js flight data (`"advertisement":{…}`: exact address with house number, the portal's point (±200 m), parameters, photos in 1560 px, 3D tours, advertiser). The description comes from its flight text row (keeps paragraphs), falling back to JSON-LD.
- Mapping notes: the portal counts storeys from 1 (ground floor = 1), so floor and floor count are reduced by one and the import warns to check it; implausible build years are dropped with a warning; no house number → street tier.
- Location: the address with house number is geocoded (Nominatim) for the exact building; otherwise the portal's point.
- Result: a demo (`demo_for` = the agency, expiry, `source_url`, noindex) with the agent's name and agency but no contacts; warnings are shown on the import page. The agent's original text is kept; "Pripraviť návrh inzerátu" in the editor can rewrite it with real distances.
- The portal already lists nearby stops/POIs with distances on the listing page, so the demo should lead with the 3D map, the one-link presentation, the AI text and lead capture, not with the distances alone.
