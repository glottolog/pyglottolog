import pathlib

from clldutils.clilib import ParserError, add_format, PathType

__all__ = ['add_output_dir']


def add_output_dir(parser):
    parser.add_argument(
        '--output',
        help='An existing directory for the output',
        type=PathType(type='dir'),
        default=pathlib.Path('.'),
    )


def register_search(parser, example):
    parser.add_argument(
        'query', metavar="QUERY", help='Search query, e.g. "{0}"'.format(example))
    add_format(parser, default='simple')


def get_languoid(args, spec):
    if spec:
        lang = args.repos.languoid(spec)
        if not lang:
            raise ParserError('Invalid languoid {0}'.format(spec))
        return lang
