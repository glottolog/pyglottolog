"""
Update benjamins.bib from a freshly compiled update.
"""
import argparse

from pyglottolog.cli_util import ExistingFile


def register(parser):
    parser.add_argument(
        'bib',
        action=ExistingFile,
        help='path to updated benjamins.bib')
    parser.add_argument(
        '--bibkey',
        default='benjamins.bib',
        help=argparse.SUPPRESS)


def run(args):  # pragma: no cover
    args.repos.bibfiles[args.bibkey].update(args.bib, log=args.log)
