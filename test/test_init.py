"""Initial testing module."""

import dvdrip


def test_version() -> None:
    version = getattr(dvdrip, "__version__", None)
    assert version is not None
    assert isinstance(version, str)
