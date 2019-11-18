"""
Index
- all bib files for use with `glottolog refsearch`
- all languoid info files for use with `glottolog langsearch`

This will take about
- about 15 minutes to create an index of about 450 MB for references and
- a couple of minutes and create an index of about 60 MB for languoids.
"""
from pyglottolog import fts


def run(args):
    fts.build_index(args.repos, args.log)
    fts.build_langs_index(args.repos, args.log)
