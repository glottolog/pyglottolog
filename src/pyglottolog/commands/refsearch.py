"""
Search Glottolog references
"""
from clldutils.clilib import Table, ParserError

from pyglottolog.cli_util import register_search
from pyglottolog import fts


def register(parser):
    register_search(parser, 'author:Haspelmath provider:wals')


def run(args):
    try:
        fts.get_index(args.repos, must_exist=True)
    except ValueError:
        raise ParserError('Index does not exist. Run "glottolog searchindex" first!')
    count, results = fts.search(args.repos, args.query)
    with Table('ID', 'Author', 'Year', 'Title') as table:
        for res in results:
            table.append([res.id, res.author, res.year, res.title])
    print('({} matches)'.format(count))
