"""
Print the classification tree starting at a specific languoid.
"""
from clldutils.clilib import ParserError

from pyglottolog.languoids import Languoid
from pyglottolog.util import sprint
from pyglottolog.cli_util import get_languoid


def register(parser):
    parser.add_argument(
        'root',
        metavar='<GLOTTOCODE>|<ISO-CODE>',
        nargs='?',
        help="Root node for the tree",
        default=None,
    )
    parser.add_argument(
        '--newick',
        help='Serialize tree in Newick format',
        default=False,
        action='store_true',
    )
    parser.add_argument(
        '--maxlevel',
        help='Maximal branch length, or maximal level of languoids to include',
        default=None,
    )
    parser.add_argument(
        '--template',
        help="""node label template, used to control the labels in the Newick string.
Values for this option must be valid python format strings expecting a single
template variable `l` which points to the Languoid instance.
In addition to Languoid attributes and properties specified as "{{l.<attr>}}",
e.g. "{{l.id}}" for the Glottocode of a Languoid, the following custom format specs
can be used:
{}""".format(
            '\n'.join('"l:{0}": {1[1]}; '.format(k, v) for k, v in Languoid._format_specs.items())),
        default=None,
    )


def run(args):
    root = get_languoid(args, args.root)

    if args.maxlevel is not None:
        try:
            args.maxlevel = int(args.maxlevel)
        except Exception:
            args.maxlevel = args.repos.languoid_levels[args.maxlevel] \
                if args.maxlevel in args.repos.languoid_levels else None
    if args.newick:
        sprint(args.repos.newick_tree(root, template=args.template, maxlevel=args.maxlevel))
    else:
        if not root:
            raise ParserError('Root languoid must be specified for non-newick serialization!')
        args.repos.ascii_tree(root, maxlevel=args.maxlevel)
