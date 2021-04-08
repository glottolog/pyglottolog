"""
Main command line interface of the pyglottolog package.
"""
import sys
import pathlib
import argparse
import contextlib

from cldfcatalog import Config, Catalog
from clldutils.clilib import register_subcommands, get_parser_and_subparsers, ParserError
from clldutils.loglib import Logging

import pyglottolog
from pyglottolog import Glottolog
import pyglottolog.commands
import pyglottolog.admin_commands


def main(**kw):
    return _main(pyglottolog.commands, **kw)


def admin_main(**kw):
    return _main(pyglottolog.admin_commands, **kw)


def _main(commands, args=None, catch_all=False, parsed_args=None, log=None, test=False):
    try:
        repos = Config.from_file().get_clone('glottolog')
    except KeyError:  # pragma: no cover
        repos = pathlib.Path('.')
    parser, subparsers = get_parser_and_subparsers('glottolog')
    parser.add_argument(
        '--repos',
        help="clone of glottolog/glottolog",
        default=repos,
        type=pathlib.Path)
    parser.add_argument(
        '--repos-version',
        help="version of repository data. Requires a git clone!",
        default=None)
    parser.add_argument(
        '--pkg-dir',
        help=argparse.SUPPRESS,
        default=pathlib.Path(__file__).parent)
    register_subcommands(subparsers, commands)

    args = parsed_args or parser.parse_args(args=args)
    args.test = test

    if not hasattr(args, "main"):
        parser.print_help()
        return 1

    with contextlib.ExitStack() as stack:
        if not log:  # pragma: no cover
            stack.enter_context(Logging(args.log, level=args.log_level))
        else:
            args.log = log
        if args.repos_version:  # pragma: no cover
            # If a specific version of the data is to be used, we make
            # use of a Catalog as context manager:
            stack.enter_context(Catalog(args.repos, tag=args.repos_version))
        try:
            args.repos = Glottolog(args.repos)
        except Exception as e:
            print(e)
            return _main(commands, args=[args._command, '-h'])
        args.log.info('glottolog/glottolog at {0}'.format(args.repos.repos))
        try:
            return args.main(args) or 0
        except KeyboardInterrupt:  # pragma: no cover
            return 0
        except ParserError as e:
            print(e)
            return _main(commands, args=[args._command, '-h'])
        except Exception as e:  # pragma: no cover
            if catch_all:
                print(e)
                return 1
            raise


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main() or 0)
