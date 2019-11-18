"""
Update iso6393.bib - the file of references for ISO 639-3 change requests.
"""
import pyglottolog.iso


def run(args):  # pragma: no cover
    pyglottolog.iso.bibtex(args.repos, args.log)
