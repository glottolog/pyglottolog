"""

"""
# Make sure we import all link providers:
from pyglottolog.links import *  # noqa: F401, F403
from pyglottolog.links.util import LinkProvider


def providers():
    return {cls.__name__.lower(): cls for cls in LinkProvider.__subclasses__()}


def register(parser):
    parser.add_argument('provider', nargs='*', help='|'.join(providers()))


def run(args):
    langs = list(args.repos.languoids())
    updated = set()
    for cls in LinkProvider.__subclasses__():
        name = cls.__name__.lower()
        if (not getattr(args, 'provider', None)) or (name in args.provider):
            args.log.info('updating {0} links ...'.format(name))
            i = 0
            for i, l in enumerate(cls().iterupdated(langs), start=1):
                l.write_info()
                updated.add(l.id)
            args.log.info('... {0} done'.format(i))
    print('{0} languoids updated'.format(len(updated)))
