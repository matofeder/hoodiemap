import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def default_config():
    from config import Config, LocationConfig, RadiiConfig, PoiConfig, CacheConfig, OutputConfig
    return Config(
        location=LocationConfig(lat=48.28646, lon=17.27221),
        radii=RadiiConfig(fetch_meters=3000, display_meters=600),
        poi=PoiConfig(),
        cache=CacheConfig(enabled=False, dir=".cache"),
        output=OutputConfig(path="output/map.png"),
    )
