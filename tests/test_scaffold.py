import importlib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent


@pytest.mark.parametrize("name", ["data", "llm", "quotes", "protocols", "judge", "run", "analyze"])
def test_modules_import(name):
    importlib.import_module(f"debate_bias.{name}")


def test_final_config_runs_on_dev_only():
    pilot = yaml.safe_load((ROOT / "configs/pilot.yaml").read_text())
    final = yaml.safe_load((ROOT / "configs/final.yaml").read_text())
    assert pilot["split"] == "train"
    assert final["split"] == "dev"
    assert pilot["protocol"] == final["protocol"]
    assert pilot["models"] == final["models"]
    assert pilot["effort"] == final["effort"]
