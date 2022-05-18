"""
Update a refprovider bib from an updated source bib.
"""
from clldutils.clilib import PathType
from clldutils.path import TemporaryDirectory

from linglit.bibtex import merge


def register(parser):
    parser.add_argument(
        'bibkey',
        choices=['benjamins', 'glossa', 'langsci', 'dplace', 'ldh', 'jocp'],
    )
    parser.add_argument(
        'bib',
        type=PathType(type='file'),
        help='path to updated source bib')
    parser.add_argument(
        '--merge',
        action='store_true',
        default=False,
    )


def run(args):  # pragma: no cover
    with TemporaryDirectory() as tmp:
        if args.merge:
            merge(args.bib, tmp / args.bib.name, delatex=True)
            args.bib = tmp / args.bib.name
        args.repos.bibfiles[args.bibkey + '.bib'].update(args.bib, log=args.log)
