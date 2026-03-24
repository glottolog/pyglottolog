"""
Write simple languoid stats to build/languoids.json.

This is to allow comparison between two branches of the repos.

Intended usage:
```
git checkout <tag>
glottolog-admin languoidstats write
git checkout <other tag>
glottolog-admin languoidstats check
```
"""
from pyglottolog.cli_util import LanguoidStats


def register(parser):  # pylint: disable=C0116
    parser.add_argument('cmd', choices=['write', 'check'])


def run(args):  # pylint: disable=C0116
    if args.cmd == 'write':
        stats = LanguoidStats.from_tree(args.repos)
        stats.to_json(args.repos)
        return

    stats = LanguoidStats.from_json(args.repos)
    stats.check({lg.id: lg for lg in args.repos.languoids()}, args.log)
