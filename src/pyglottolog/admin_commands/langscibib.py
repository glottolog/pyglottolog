"""
Update langsci.bib
"""
import re
import argparse
import collections

from clldutils.misc import slug
from clldutils.clilib import PathType
from pyglottolog.references.bibtex import iterentries


def register(parser):
    parser.add_argument(
        'bib',
        type=PathType(type='file'),
        help='path to updated langsci.bib')
    parser.add_argument(
        '--bibkey',
        default='langsci.bib',
        help=argparse.SUPPRESS)


def run(args):  # pragma: no cover
    args.repos.bibfiles[args.bibkey].update(args.bib, log=args.log)
    return
    #
    # FIXME: First update keys in old langsci.bib to the new ones based on
    #  - old citation key
    #  - title
    #
    titles = {}
    keys = {}
    by_stem = collections.defaultdict(dict)

    for key, (_, fields) in iterentries(args.bib):
        keys[key] = 1
        if re.search(r':[0-9]{2}:[0-9]$', key) and fields.get('title'):
            by_stem[':'.join(key.split(':')[:-1])][slug(fields['title'])] = key
        if fields.get('title'):
            titles[key] = slug(fields['title'])

    bib = args.repos.bibfiles[args.bibkey]

    def visitor(e):
        e.type = e.type.lower()
        lookup = e.key.lower()
        if lookup in keys:
            e.key = lookup
            return

        if lookup[-1] in 'abc':
            lookup = lookup[:-1]

        if lookup in by_stem:
            tslug = slug(e.fields.get('title', ''))
            if tslug in by_stem[lookup]:
                e.key = by_stem[lookup][tslug]
                return

        if ':ed:' in lookup:
            lookup = lookup.replace(':ed:', ':')
            if lookup in titles:
                if slug(e.fields.get('title', '')) == titles[lookup]:
                    e.key = lookup
                    return

        return True
    bib.visit(visitor)
