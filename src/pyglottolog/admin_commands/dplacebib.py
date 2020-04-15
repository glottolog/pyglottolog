"""
Update dplace.bib from a freshly compiled update.
"""
import argparse

from clldutils.clilib import PathType


def register(parser):
    parser.add_argument(
        'bib',
        type=PathType(type='file'),
        help='path to updated benjamins.bib')
    parser.add_argument(
        '--bibkey',
        default='dplace.bib',
        help=argparse.SUPPRESS)


def run(args):  # pragma: no cover
    args.repos.bibfiles[args.bibkey].update(args.bib, log=args.log)
