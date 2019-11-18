"""
Dump Glottolog data as CLDF dataset
"""
import pathlib

from pyglottolog import cldf


def register(parser):
    parser.add_argument(
        'cldf_dir',
        type=pathlib.Path,
        help='path to clone of glottolog/glottolog-cldf')


def run(args):
    cldf.cldf(args.repos, args.cldf_dir, args.log)
