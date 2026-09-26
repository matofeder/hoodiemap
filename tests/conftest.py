import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def default_config(tmp_path):
    from config import CacheConfig, Config, LocationConfig, RadiiConfig
    return Config(
        location=LocationConfig(lat=48.28646, lon=17.27221),
        radii=RadiiConfig(display_meters=140),
        cache=CacheConfig(enabled=False, dir=str(tmp_path / "cache")),
    )
