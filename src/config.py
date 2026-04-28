from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class LocationConfig(BaseModel):
    lat: float
    lon: float


class RadiiConfig(BaseModel):
    fetch_meters: float = 3000.0
    display_meters: float = 600.0


class PoiShowConfig(BaseModel):
    hospital: bool = True
    grocery: bool = True
    school: bool = True
    pharmacy: bool = True
    pub: bool = True
    bar: bool = True
    restaurant: bool = True
    public_office: bool = True


class PoiConfig(BaseModel):
    max_per_category: int = 3
    show: PoiShowConfig = Field(default_factory=PoiShowConfig)


class CacheConfig(BaseModel):
    enabled: bool = True
    dir: str = ".cache"


class OutputConfig(BaseModel):
    path: str = "output/map.png"


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class Config(BaseModel):
    location: LocationConfig
    radii: RadiiConfig = Field(default_factory=RadiiConfig)
    poi: PoiConfig = Field(default_factory=PoiConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)


def load_config(path: str | Path = "config.yaml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config.model_validate(data)
