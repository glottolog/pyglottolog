"""
Utilities used in Glottolog commands.
"""
import pathlib
from typing import TYPE_CHECKING, Optional

from clldutils.clilib import ParserError, PathType

if TYPE_CHECKING:
    from pyglottolog.languoids import Languoid

__all__ = ['add_output_dir', 'get_languoid']


def add_output_dir(parser):
    """Add an option specifying an output directory."""
    parser.add_argument(
        '--output',
        help='An existing directory for the output',
        type=PathType(type='dir'),
        default=pathlib.Path('.'),
    )


def get_languoid(args, spec: str) -> Optional['Languoid']:
    """Get a languoid."""
    if spec:
        lang = args.repos.languoid(spec)
        if not lang:
            raise ParserError(f'Invalid languoid {spec}')
        return lang
    return None
