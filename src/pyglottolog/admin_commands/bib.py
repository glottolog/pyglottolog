"""
Compile the monster bibfile from the BibTeX files listed in references/BIBFILES.ini
"""
from pyglottolog.monster import compile  # pylint: disable=redefined-builtin


def run(args):  # pylint: disable=C0116
    compile(args.repos, args.log)
