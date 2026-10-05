"""
Shared test compatibility import: stdlib ``tomllib`` on 3.11+, ``tomli`` on 3.10.

Usage in test modules::

    from tests._compat import tomllib
"""

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

__all__ = ["tomllib"]
