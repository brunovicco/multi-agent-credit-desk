"""Contract test tying infra/litellm/config.yaml to credit_desk_contracts.enums.ModelGroup.

Static-only: parses the YAML file directly, no network access and no litellm import (litellm is
not a workspace dependency - the proxy is only exercised by the running infra stack, per
docs/DEVELOPMENT.md's ``pytest -m integration`` instructions).
"""

from pathlib import Path
from typing import Any, cast

import yaml

from credit_desk_contracts.enums import ModelGroup

CONFIG_PATH = Path(__file__).resolve().parents[2] / "infra" / "litellm" / "config.yaml"


def _load_config() -> dict[str, Any]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data)


def test_model_list_covers_every_model_group_exactly() -> None:
    config = _load_config()
    model_names = {entry["model_name"] for entry in config["model_list"]}

    assert model_names == {group.value for group in ModelGroup}


def test_every_deployment_references_an_env_var_api_key_not_a_literal() -> None:
    config = _load_config()

    for entry in config["model_list"]:
        api_key = entry["litellm_params"]["api_key"]
        assert api_key.startswith("os.environ/"), (
            f"{entry['model_name']} must reference an env var, not embed a literal API key"
        )


def test_general_settings_master_key_references_an_env_var() -> None:
    config = _load_config()

    assert config["general_settings"]["master_key"].startswith("os.environ/")


def test_no_cross_group_fallbacks_are_configured() -> None:
    config = _load_config()

    assert "fallbacks" not in config.get("router_settings", {})
