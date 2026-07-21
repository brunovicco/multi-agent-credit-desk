"""Behavior tests for decisao-agent's Agent Card construction."""

from decisao_agent.entrypoints.agent_card import build_agent_card

_BASE_URL = "http://127.0.0.1:9999"


def test_build_agent_card_advertises_the_given_base_url() -> None:
    card = build_agent_card(_BASE_URL)

    assert len(card.supported_interfaces) == 1
    assert card.supported_interfaces[0].url == _BASE_URL
    assert card.supported_interfaces[0].protocol_binding == "JSONRPC"


def test_build_agent_card_declares_exactly_one_skill() -> None:
    card = build_agent_card(_BASE_URL)

    assert len(card.skills) == 1
    skill = card.skills[0]
    assert skill.id == "evaluate_credit_application"
    assert list(skill.input_modes) == ["application/json"]
    assert list(skill.output_modes) == ["application/json"]


def test_build_agent_card_does_not_advertise_streaming() -> None:
    card = build_agent_card(_BASE_URL)

    assert card.capabilities.streaming is False


def test_build_agent_card_default_modes_match_the_skill_modes() -> None:
    card = build_agent_card(_BASE_URL)

    assert list(card.default_input_modes) == ["application/json"]
    assert list(card.default_output_modes) == ["application/json"]
