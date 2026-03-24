"""
Command to update the elpubbib ref provider.
"""
from pyglottolog.references.elpubbib import download


def run(args):  # pragma: no cover  # pylint: disable=C0116
    download(args.repos.bibfiles['elpub.bib'], args.log, args.repos)
