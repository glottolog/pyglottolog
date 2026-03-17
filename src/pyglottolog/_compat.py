"""
Python compatibility backports
"""
import sys

__all__ = ['StrEnum']


if sys.version_info >= (3, 11):
    from enum import StrEnum
    assert StrEnum
else:
    from backports.strenum import StrEnum  # pragma: no cover
