"""Package smoke tests."""


def test_package_is_importable() -> None:
    """Ensure the generated package is importable."""
    import credit_desk_contracts  # noqa: F401
