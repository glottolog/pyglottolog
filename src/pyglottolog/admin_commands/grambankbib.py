"""

"""
import pathlib
import tempfile
import urllib.request


def register(parser):
    parser.add_argument('bib', help='URL to download grambank.bib')


def run(args):  # pragma: no cover
    fname = pathlib.Path(tempfile.gettempdir()) / 'grambank.bib'
    urllib.request.urlretrieve(args.bib, fname)
    bibfile = args.repos.bibfiles['grambank.bib']
    bibfile.update(fname, log=args.log)
    bibfile.check(args.log)
    fname.unlink()
