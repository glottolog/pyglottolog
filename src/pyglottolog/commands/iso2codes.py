"""
Map ISO codes to the list of all Glottolog languages and dialects subsumed "under" it.
"""
from csvw.dsv import UnicodeWriter

from pyglottolog.cli_util import add_output_dir


def register(parser):
    add_output_dir(parser)


def run(args):
    nodes = list(args.repos.languoids())

    res = {}
    for node in nodes:
        if node.iso:
            res[node.id] = (node.iso, set())

    for node in nodes:
        if node.level == args.repos.languoid_levels.family or node.id in res:
            continue
        for nid in res:
            matched = False
            for l in node.lineage:
                if l[1] == nid:
                    res[nid][1].add(node.id)
                    matched = True
                    break
            if matched:
                break

    with UnicodeWriter(args.output / 'iso2glottocodes.csv') as writer:
        writer.writerow(['iso', 'glottocodes'])
        for gc, (iso, gcs) in res.items():
            writer.writerow([iso, ';'.join([gc] + list(gcs))])
