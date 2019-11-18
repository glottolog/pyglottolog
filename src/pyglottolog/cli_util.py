import pathlib
import argparse

from clldutils.clilib import ParserError, add_format

__all__ = ['add_output_dir', 'ExistingDir', 'ExistingFile']


class ExistingFile(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        d = pathlib.Path(value)
        if not (d.exists() and d.is_file()):
            raise argparse.ArgumentError(None, '{0} must be an existing file'.format(self.dest))
        setattr(namespace, self.dest, d)


class ExistingDir(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        d = pathlib.Path(value)
        if not (d.exists() and d.is_dir()):
            raise argparse.ArgumentError(
                None, '{0} must be an existing directory'.format(self.dest))
        setattr(namespace, self.dest, d)


def add_output_dir(parser):
    parser.add_argument(
        '--output',
        help='An existing directory for the output',
        default=pathlib.Path('.'),
        action=ExistingDir)


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
