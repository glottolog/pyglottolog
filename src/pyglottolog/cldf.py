import collections

from pycldf import StructureDataset, Source
from pycldf.dataset import GitRepository

import pyglottolog


def value(lid, pid, value, **kw):
    res = dict(
        ID='{0}-{1}'.format(lid, pid),
        Language_ID=lid,
        Parameter_ID=pid,
        Value=value,
    )
    res.update(**kw)
    return res


def repos(name, **kw):
    return GitRepository('https://github.com/glottolog/{0}'.format(name), **kw)


def cldf(api, outdir, log):
    if not outdir.exists():
        outdir.mkdir()
    for p in outdir.iterdir():
        if p.suffix in ['.bib', '.csv', '.json']:
            p.unlink()
    ds = StructureDataset.in_dir(outdir)
    ds.add_provenance(
        wasDerivedFrom=repos('glottolog', clone=api.repos),
        wasGeneratedBy=repos('pyglottolog', version=pyglottolog.__version__),
    )
    ds.add_component('ParameterTable', {'name': 'type', 'default': None})
    ds.add_component('CodeTable', 'numerical_value')
    ds.add_columns('ValueTable', 'codeReference')
    ds.add_component(
        'LanguageTable',
        dict(name='Countries', separator=';'),
        {
            'name': 'Family_ID',
            'dc:description': 'Glottocode of the top-level genetic unit, the '
            'languoid belongs to'},
        {
            'name': 'Language_ID',
            'dc:description': 'Glottocode of the language-level languoid, the '
            'languoid belongs to (in case of dialects)'},
    )
    ds.add_foreign_key('LanguageTable', 'Family_ID', 'LanguageTable', 'ID')
    ds.add_foreign_key('LanguageTable', 'Language_ID', 'LanguageTable', 'ID')

    ds['LanguageTable', 'Macroarea'].separator = ';'
    ds['ValueTable', 'Value'].null = ['<NA>']

    data = collections.defaultdict(list)
    data['ParameterTable'].extend([
        dict(ID='level', Name='Level', type='categorical'),
        dict(ID='category', Name='Category', type='categorical'),
        dict(ID='classification', Name='Classification'),
        dict(ID='subclassification', Name='Subclassification'),
        dict(ID='aes', Name='Agglomerated Endangerment Status', type='sequential'),
        dict(ID='med', Name='Most Extensive Description', type='sequential'),
    ])
    for level in api.languoid_levels.values():
        data['CodeTable'].append(dict(
            ID='level-{0}'.format(level.name),
            Parameter_ID='level',
            Name=level.name,
            Description=level.description,
            numerical_value=level.ordinal))
        data['CodeTable'].append(dict(
            ID='category-{0}'.format(level.name.capitalize()),
            Parameter_ID='category',
            Name=level.name.capitalize()))
    for el in sorted(api.language_types.values()):
        data['CodeTable'].append(dict(
            ID='category-{0}'.format(el.category.replace(' ', '_')),
            Parameter_ID='category',
            Name=el.category))
    for el in sorted(api.aes_status.values()):
        data['CodeTable'].append(dict(
            ID='aes-{0}'.format(el.name.replace(' ', '_')),
            Parameter_ID='aes',
            Name=el.name,
            numerical_value=el.ordinal))
    for el in sorted(api.med_types.values()):
        data['CodeTable'].append(dict(
            ID='med-{0}'.format(el.id),
            Parameter_ID='med',
            Name=el.name,
            Description=el.description,
            numerical_value=el.rank))
    languoids = collections.OrderedDict((l.id, l) for l in api.languoids())
    refs_by_languoid, refs = api.refs_by_languoid(languoids)

    def get_language_id(l):
        if l.level == api.languoid_levels.dialect:
            for _, lid, _ in reversed(l.lineage):
                if languoids[lid].level == api.languoid_levels.language:
                    return lid

    def format_ref(ref):
        return '{0}[{1}]'.format(ref.key, ref.pages.replace(';', ',')) if ref.pages else ref.key

    for l in languoids.values():
        data['LanguageTable'].append(dict(
            ID=l.id,
            Name=l.name,
            Glottocode=l.id,
            ISO639P3code=l.iso,
            Latitude=l.latitude,
            Longitude=l.longitude,
            Macroarea=[ma.name for ma in l.macroareas],
            Countries=[c.id for c in l.countries],
            Family_ID=l.lineage[0][1] if l.lineage else None,
            Language_ID=get_language_id(l),
        ))
        med = sorted(refs_by_languoid[l.id], reverse=True)[0] if l.id in refs_by_languoid else None
        if med:
            ds.add_sources(Source(med.type, med.id, _check_id=False, **med.fields))
        clf = l.classification_comment
        if clf:
            for ref in clf.merged_refs('family') + clf.merged_refs('sub'):
                if ref.key not in refs:
                    log.warning('missing reference in classification comment: {0}'.format(ref))
                    continue
                e = refs[ref.key]
                ds.add_sources(Source(e.type, ref.key, _check_id=False, **e.fields))

        aes_src = l.endangerment.source.reference_id if l.endangerment else None
        if aes_src:
            e = refs[aes_src]
            ds.add_sources(Source(e.type, aes_src, _check_id=False, **e.fields))

        data['ValueTable'].extend([
            value(
                l.id,
                'level',
                l.level.name,
                Code_ID='level-{0}'.format(l.level.name)),
            value(l.id, 'category', l.category.replace(' ', '_')),
            value(
                l.id,
                'classification',
                '/'.join(l[1] for l in l.lineage),
                Source=[format_ref(ref) for ref in clf.merged_refs('family')] if clf else [],
                Comment=clf.family if clf else None,
            ),
            value(
                l.id,
                'subclassification',
                l.newick_node(nodes=languoids, template="{l.id}").newick,
                Source=[format_ref(ref) for ref in clf.merged_refs('sub')] if clf else [],
                Comment=clf.sub if clf else None,
            ),
            value(
                l.id,
                'aes',
                l.endangerment.status.name if l.endangerment else None,
                Comment=l.endangerment.comment if l.endangerment else None,
                Source=[aes_src] if aes_src else [],
                Code_ID='aes-{0}'.format(
                    l.endangerment.status.name.replace(' ', '_')) if l.endangerment else None),
            value(
                l.id,
                'med',
                med.med_type.name if med else None,
                Source=[med.id] if med else [],
                Code_ID='med-{0}'.format(med.med_type.id) if med else None),
        ])

    ds.write(outdir / 'cldf-metadata.json', **data)
    ds.validate(log=log)
