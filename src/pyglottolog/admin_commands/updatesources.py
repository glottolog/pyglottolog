"""
Update the [sources] section in languoid info files according to `lgcode` fields in bibfiles.
"""
import collections

from pyglottolog.languoids import Reference


def run(args):
    langs = args.repos.languoids_by_code()
    updated = []
    sources = collections.defaultdict(set)
    glrefs = set()

    for entry in args.repos.bibfiles['hh.bib'].iterentries():
        for lang in entry.languoids(langs)[0]:
            sources[lang.id].add('{0}:{1}'.format('hh', entry.key))
            if entry.fields.get('glottolog_ref_id'):
                glrefs.add(entry.fields['glottolog_ref_id'])

    for bib in args.repos.bibfiles:
        if bib.id == 'hh':
            continue
        for entry in bib.iterentries():
            # If language associations have already been read from an equivalent record in hh.bib,
            # we disregard the entry.
            if entry.fields.get('glottolog_ref_id') not in glrefs:
                for lang in entry.languoids(langs)[0]:
                    sources[lang.id].add('{0}:{1}'.format(bib.id, entry.key))

    for gc, refs in sources.items():
        if refs != set(r.key for r in langs[gc].sources):
            langs[gc].sources = [Reference(key=ref) for ref in sorted(refs)]
            langs[gc].write_info()
            updated.append(gc)
    print('{0} languoids updated'.format(len(updated)))
