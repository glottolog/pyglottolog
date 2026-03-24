"""
Update a refprovider bib from an updated source bib.
"""
from clldutils.clilib import PathType
from clldutils.path import TemporaryDirectory

from linglit.bibtex import merge


def register(parser):  # pylint: disable=C0116
    parser.add_argument(
        'bibkey',
        choices=['cldf', 'benjamins', 'glossa', 'langsci', 'dplace', 'ldh', 'jocp'],
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


def run(args):  # pragma: no cover  # pylint: disable=C0116
    with TemporaryDirectory() as tmp:
        if args.merge:
            merge(args.bib, tmp / args.bib.name, delatex=True)
            args.bib = tmp / args.bib.name
        args.repos.bibfiles[args.bibkey + '.bib'].update(args.bib, log=args.log)
