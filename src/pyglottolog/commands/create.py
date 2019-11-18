"""
Create a new languoid directory for a languoid specified by name and level.
"""
import pathlib

from clldutils.clilib import ParserError

from pyglottolog.languoids import Glottocode, Languoid
from pyglottolog.cli_util import get_languoid


def register(parser):
    parser.add_argument(
        'parent',
        help='Parent languoid specified by Glottocode or directory',
    )
    parser.add_argument(
        'name',
        help='Name of the new languoid',
    )
    parser.add_argument(
        'level',
        help='Level of the languoid',
        choices=['family', 'language', 'dialect']
    )
    parser.add_argument(
        'props',
        nargs='*',
        help='Additional properties to populate the [core] section, given as prop=value pairs',
    )


def run(args):
    if Glottocode.pattern.match(args.parent):
        args.parent = get_languoid(args, args.parent).dir
    else:
        args.parent = pathlib.Path(args.parent)
        if not args.parent.exists():
            raise ParserError('invalid parent dir specified')

    lang = Languoid.from_name_id_level(
        args.parent,
        args.name,
        args.repos.glottocodes.new(args.name),
        args.level,
        **dict(prop.split('=') for prop in args.props))

    print("Info written to %s" % lang.write_info(outdir=args.parent))
