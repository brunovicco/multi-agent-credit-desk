"""Package smoke tests."""


def test_package_is_importable() -> None:
    """Ensure the generated package is importable."""
    import multi_agent_credit_desk  # noqa: F401
