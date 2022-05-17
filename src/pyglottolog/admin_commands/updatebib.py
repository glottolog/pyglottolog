"""
Update a refprovider bib from an updated source bib.
"""
from clldutils.clilib import PathType


def register(parser):
    parser.add_argument(
        'bibkey',
        choices=['benjamins', 'glossa', 'langsci', 'dplace', 'evobib'],
    )
    parser.add_argument(
        'bib',
        type=PathType(type='file'),
        help='path to updated source bib')


def run(args):  # pragma: no cover
    args.repos.bibfiles[args.bibkey + '.bib'].update(args.bib, log=args.log)
