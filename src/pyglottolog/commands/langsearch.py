"""
Search Glottolog languoids.

Note: The search index will be created upon first invocation of this command.
"""
import re
import pathlib

from termcolor import colored

from pyglottolog import fts
from pyglottolog.cli_util import register_search
from pyglottolog.util import sprint


def register(parser):
    register_search(parser, 'iso:abd')


def run(args):
    def highlight(text):
        res, i = '', 0
        for m in re.finditer(r'\[\[(?P<m>[^]]+)]]', text):
            res += text[i:m.start()]
            res += colored(m.group('m'), 'red', attrs=['bold'])
            i = m.end()
        res += text[i:]
        return res + '\n'

    count, results = fts.search_langs(args.repos, args.query)
    print('{} matches'.format(count))
    for res in results:
        try:
            p = pathlib.Path(res.fname).relative_to(pathlib.Path.cwd())
        except ValueError:
            p = res.fname
        sprint('{0.name} [{0.id}] {0.level}'.format(res), color=None, attrs=['bold'])
        sprint(p, color='green')
        sprint(highlight(res.highlights) if res.highlights else '')
    print('{} matches'.format(count))
