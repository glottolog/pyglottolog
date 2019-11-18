"""
Open a languoid's INI file in a text editor.
"""
import sys
import subprocess

from pyglottolog.cli_util import get_languoid


def register(parser):
    parser.add_argument(
        'languoid',
        metavar='<GLOTTOCODE>|<ISO-CODE>',
    )


def run(args):
    lang = get_languoid(args, args.languoid)
    if sys.platform.startswith('os2'):  # pragma: no cover
        cmd = 'open'
    elif sys.platform.startswith('linux'):
        cmd = 'xdg-open'
    elif sys.platform.startswith('win'):  # pragma: no cover
        cmd = 'notepad.exe'
    else:  # pragma: no cover
        print(lang.fname)
        return
    subprocess.call([cmd, str(lang.fname)])
