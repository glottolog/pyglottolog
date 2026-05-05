"""
Update links.
"""
# Make sure we import all link providers:
from pyglottolog.links import *  # noqa: F401, F403  # pylint: disable=W0614,W0401
from pyglottolog.links.util import LinkProvider


def providers():  # pylint: disable=C0116
    return {cls.__name__.lower(): cls for cls in LinkProvider.__subclasses__()}


def register(parser):  # pylint: disable=C0116
    parser.add_argument('provider', nargs='*', help='|'.join(providers()))


def run(args):  # pylint: disable=C0116
    langs = list(args.repos.languoids())
    updated = set()
    for cls in LinkProvider.__subclasses__():
        if getattr(cls, '__inactive__', False):
            continue
        name = cls.__name__.lower()
        if (not getattr(args, 'provider', None)) or (name in args.provider):
            args.log.info(f'updating {name} links ...')
            i = 0
            for i, l in enumerate(cls(args.repos).iterupdated(langs), start=1):
                l.write_info()
                updated.add(l.id)
            args.log.info(f'... {i} done')
    print(f'{len(updated)} languoids updated')
