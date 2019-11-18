"""
Compile the monster bibfile from the BibTeX files listed in references/BIBFILES.ini
"""
from pyglottolog.monster import compile


def register(parser):
    parser.add_argument(
        '--rebuild',
        default=False,
        action='store_true',
    )


def run(args):
    compile(args.repos, args.log, rebuild=args.rebuild)
