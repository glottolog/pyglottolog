"""
Write release info to .zenodo.json, CITATION.md and CONTRIBUTORS.md
"""
from pyglottolog.metadata import prepare_release


def register(parser):
    parser.add_argument('version')


def run(args):
    prepare_release(args.repos, args.version)
