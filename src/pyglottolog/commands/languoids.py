"""
Write languoids data to csv files
"""
from pyglottolog.cli_util import add_output_dir


def register(parser):
    add_output_dir(parser)


def run(args):
    res = args.repos.write_languoids_table(args.output, args.repos_version)
    print('Lagnuoids table written to')
    for p in res:
        print('{0}'.format(p))
