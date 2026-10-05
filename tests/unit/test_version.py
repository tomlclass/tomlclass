"""
Tests for package metadata.
"""

import re

import tomlclass


class TestVersion:
    def test_version_format(self):
        # SemVer-ish: major.minor.patch
        assert re.fullmatch(r"\d+\.\d+\.\d+", tomlclass.__version__)

    def test_core_exports_present(self):
        for name in tomlclass.__all__:
            assert hasattr(tomlclass, name), f"{name} declared in __all__ but missing"
        for name in ("parse", "load", "dumps", "Document", "Config", "Field"):
            assert name in tomlclass.__all__
        assert isinstance(tomlclass.__version__, str)
