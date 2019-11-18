"""
Update retirement info in language info files.
"""
import pyglottolog.iso


def run(args):  # pragma: no cover
    pyglottolog.iso.retirements(args.repos, args.log)
