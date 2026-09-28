from pathlib import Path

import yaml
from pydantic import BaseModel, Field


PUBLIC_OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


class LocationConfig(BaseModel):
    lat: float
    lon: float


class RadiiConfig(BaseModel):
    display_meters: float = 140.0  # address tier
    street_min: float = 160.0
    street_max: float = 300.0
    city_meters: float = 450.0


class PoiShowConfig(BaseModel):
    hospital: bool = True
    supermarket: bool = True
    school: bool = True
    kindergarten: bool = True
    pharmacy: bool = True
    bus_stop: bool = True
    train: bool = True
    park: bool = True
    playground: bool = True
    food: bool = True
    post: bool = True
    bank: bool = True
    doctors: bool = True
    city: bool = True
    bus_station: bool = True
    mall: bool = True
    landmark: bool = True


class PoiConfig(BaseModel):
    show: PoiShowConfig = Field(default_factory=PoiShowConfig)

    def enabled(self) -> list[str]:
        return [name for name, on in self.show.model_dump().items() if on]


class CacheConfig(BaseModel):
    enabled: bool = True
    dir: str = ".cache"


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class GeocodeConfig(BaseModel):
    countrycodes: str = "sk"


class OverpassConfig(BaseModel):
    local_url: str | None = None  # None: public servers only
    public_endpoints: list[str] = Field(default_factory=lambda: list(PUBLIC_OVERPASS))
    local_bbox: tuple[float, float, float, float] = (47.73, 16.83, 49.61, 22.57)  # S, W, N, E of the extract


class Config(BaseModel):
    location: LocationConfig
    radii: RadiiConfig = Field(default_factory=RadiiConfig)
    poi: PoiConfig = Field(default_factory=PoiConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    geocode: GeocodeConfig = Field(default_factory=GeocodeConfig)
    overpass: OverpassConfig = Field(default_factory=OverpassConfig)


def load_config(path: str | Path = "config.yaml") -> Config:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config.model_validate(data)
