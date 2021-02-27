"""
List all metadata fields used in languoid INI files and their frequency.
"""
import collections

from clldutils.clilib import Table, add_format


def register(parser):
    add_format(parser)


def run(args):
    ops = collections.defaultdict(collections.Counter)

    for lang in args.repos.languoids():
        for secname, sec in lang.cfg.items():
            ops[secname].update(opt for opt, val in sec.items() if val)

    ops.pop('DEFAULT', None)

    with Table('section', 'option', 'count') as table:
        for section, options in ops.items():
            table.append([section, '', float(sum(options.values()))])
            for k, n in options.most_common():
                table.append(['', k, float(n)])
