from pathlib import Path

from config import PoiConfig, PoiShowConfig, load_config

ALL = ["hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park",
       "playground", "food", "post", "bank", "doctors", "city", "bus_station", "mall", "landmark"]


def test_default_enables_all_categories():
    assert PoiConfig().enabled() == ALL


def test_enabled_lists_only_true_categories():
    show = PoiShowConfig(**{name: name in ("hospital", "pharmacy") for name in ALL})
    assert PoiConfig(show=show).enabled() == ["hospital", "pharmacy"]


def test_repo_config_loads():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.radii.display_meters == 140
    assert cfg.poi.enabled() == ALL


def test_tier_radii_and_geocode_defaults():
    from config import Config, LocationConfig
    cfg = Config(location=LocationConfig(lat=48.0, lon=17.0))
    assert (cfg.radii.display_meters, cfg.radii.street_min, cfg.radii.street_max, cfg.radii.city_meters) == (140, 160, 300, 450)
    assert cfg.geocode.countrycodes == "sk"


def test_repo_config_has_tier_settings():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.radii.city_meters == 450 and cfg.radii.street_max == 300
    assert cfg.geocode.countrycodes == "sk"


def test_geocode_limited_to_slovakia():
    from config import Config, LocationConfig
    assert Config(location=LocationConfig(lat=48.0, lon=17.0)).geocode.countrycodes == "sk"
    assert load_config(Path(__file__).parent.parent / "config.yaml").geocode.countrycodes == "sk"


def test_overpass_defaults_keep_todays_behaviour():
    from config import Config, LocationConfig
    cfg = Config(location=LocationConfig(lat=48.0, lon=17.0))
    assert cfg.overpass.local_url is None
    assert cfg.overpass.public_endpoints == [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]
    assert cfg.overpass.local_bbox == (47.73, 16.83, 49.61, 22.57)


def test_repo_config_enables_local_overpass():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.overpass.local_url == "http://localhost:12345/api/interpreter"
