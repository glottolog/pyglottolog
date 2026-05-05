"""
Create lff.txt and dff.txt from the current languoid tree.
"""
from pyglottolog import lff


def run(args):  # pylint: disable=C0116
    lff.tree2lff(args.repos, args.log)
