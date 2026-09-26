from pathlib import Path

from config import PoiConfig, PoiShowConfig, load_config

ALL = ["hospital", "supermarket", "school", "kindergarten", "pharmacy", "bus_stop", "train", "park",
       "playground", "food", "post", "bank", "doctors", "city"]


def test_default_enables_all_categories():
    assert PoiConfig().enabled() == ALL


def test_enabled_lists_only_true_categories():
    show = PoiShowConfig(**{name: name in ("hospital", "pharmacy") for name in ALL})
    assert PoiConfig(show=show).enabled() == ["hospital", "pharmacy"]


def test_repo_config_loads():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert cfg.radii.display_meters == 140
    assert cfg.poi.enabled() == ALL
