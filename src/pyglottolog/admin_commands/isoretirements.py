"""
Update retirement info in language info files.
"""
import pyglottolog.iso


def run(args):  # pragma: no cover  # pylint: disable=C0116
    pyglottolog.iso.retirements(args.repos, args.log)
