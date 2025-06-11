"""

"""
from clldutils.markup import MarkdownLink


def run(args):
    elcat2cldf = {}
    for e in args.repos.bibfiles['cldf.bib'].iterentries():
        for key in e.fields['citekeys'].split():
            if key.startswith('cldf9:'):
                elcat2cldf['elcat:' + key.split(':')[-1]] = e.id

    def repl(ml):
        if ml.url.startswith('elcat:'):
            assert ml.url in elcat2cldf, ml.url
            ml.url = elcat2cldf[ml.url]
        return ml

    changed = 0
    for lg in args.repos.languoids():
        if lg.endangerment and lg.endangerment.comment:
            cmt = MarkdownLink.replace(lg.endangerment.comment, repl)
            if cmt != lg.endangerment.comment:
                changed += 1
                lg.cfg['endangerment']['comment'] = cmt
                lg.write_info()
    print(changed)
