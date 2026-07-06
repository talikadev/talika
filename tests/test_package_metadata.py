from importlib.metadata import version

import talika


def test_public_version_matches_distribution_metadata():
    assert talika.__version__ == version("talika")


def test_public_all_exports_are_available_at_top_level():
    assert talika.__all__
    for name in talika.__all__:
        assert getattr(talika, name)
