"""
Create lff.txt and dff.txt from the current languoid tree.
"""
from pyglottolog import lff


def run(args):
    lff.tree2lff(args.repos, args.log)
