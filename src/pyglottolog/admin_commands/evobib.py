"""
Command to update the evobib ref provider.
"""
from clldutils.clilib import PathType

from pyglottolog.references import evobib


def register(parser):  # pylint: disable=C0116
    parser.add_argument(
        'bib',
        type=PathType(type='file'),
        help='path to downloaded evobib-converted.bib')


def run(args):  # pragma: no cover  # pylint: disable=C0116
    evobib.update(args.bib, args.repos.bibfiles['evobib.bib'], args.log)
