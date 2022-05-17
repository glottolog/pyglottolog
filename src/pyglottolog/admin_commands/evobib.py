"""
"""
from clldutils.clilib import PathType

from pyglottolog.references import evobib


def register(parser):
    parser.add_argument(
        'bib',
        type=PathType(type='file'),
        help='path to downloaded evobib-converted.bib')


def run(args):  # pragma: no cover
    evobib.update(args.bib, args.repos.bibfiles['evobib.bib'], args.log)
