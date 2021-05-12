import collections

from pycldf import Source


def value(lid, pid, value, **kw):
    res = dict(
        ID='{0}-{1}'.format(lid, pid),
        Language_ID=lid,
        Parameter_ID=pid,
        Value=value,
    )
    res.update(**kw)
    return res


def cldf(ds, data, api, log):
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
        data['CodeTable'].append(dict(
            ID='category-Pseudo_{0}'.format(level.name.capitalize()),
            Parameter_ID='category',
            Name='Pseudo {}'.format(level.name.capitalize())))
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
    languoids = collections.OrderedDict((lang.id, lang) for lang in api.languoids())
    refs_by_languoid, refs = api.refs_by_languoid(languoids)

    def get_language_id(lang):
        if lang.level == api.languoid_levels.dialect:
            for _, lid, _ in reversed(lang.lineage):
                if languoids[lid].level == api.languoid_levels.language:
                    return lid

    def format_ref(ref):
        return '{0}[{1}]'.format(ref.key, ref.pages.replace(';', ',')) if ref.pages else ref.key

    for lang in languoids.values():
        data['LanguageTable'].append(dict(
            ID=lang.id,
            Name=lang.name,
            Glottocode=lang.id,
            ISO639P3code=lang.iso,
            Latitude=lang.latitude,
            Longitude=lang.longitude,
            Macroarea=[ma.name for ma in lang.macroareas],
            Countries=[c.id for c in lang.countries],
            Family_ID=lang.lineage[0][1] if lang.lineage else None,
            Language_ID=get_language_id(lang),
        ))
        med = sorted(refs_by_languoid[lang.id], reverse=True)[0] \
            if lang.id in refs_by_languoid else None
        if med:
            ds.add_sources(Source(med.type, med.id, _check_id=False, **med.fields))
        clf = lang.classification_comment
        if clf:
            for ref in clf.merged_refs('family') + clf.merged_refs('sub'):
                if ref.key not in refs:
                    log.warning('missing reference in classification comment: {0}'.format(ref))
                    continue
                e = refs[ref.key]
                ds.add_sources(Source(e.type, ref.key, _check_id=False, **e.fields))

        aes_src = lang.endangerment.source.reference_id if lang.endangerment else None
        if aes_src:
            e = refs[aes_src]
            ds.add_sources(Source(e.type, aes_src, _check_id=False, **e.fields))

        data['ValueTable'].extend([
            value(
                lang.id,
                'level',
                lang.level.name,
                Code_ID='level-{0}'.format(lang.level.name)),
            value(
                lang.id,
                'category',
                lang.category.replace(' ', '_'),
                Code_ID='category-{0}'.format(lang.category.replace(' ', '_')),
            ),
            value(
                lang.id,
                'classification',
                '/'.join(li[1] for li in lang.lineage),
                Source=[format_ref(ref) for ref in clf.merged_refs('family')] if clf else [],
                Comment=clf.family if clf else None,
            ),
            value(
                lang.id,
                'subclassification',
                lang.newick_node(nodes=languoids, template="{l.id}").newick + ';',
                Source=[format_ref(ref) for ref in clf.merged_refs('sub')] if clf else [],
                Comment=clf.sub if clf else None,
            ),
            value(
                lang.id,
                'aes',
                lang.endangerment.status.name if lang.endangerment else None,
                Comment=lang.endangerment.comment if lang.endangerment else None,
                Source=[aes_src] if aes_src else [],
                Code_ID='aes-{0}'.format(lang.endangerment.status.name.replace(' ', '_'))
                if lang.endangerment else None),
            value(
                lang.id,
                'med',
                med.med_type.name if med else None,
                Source=[med.id] if med else [],
                Code_ID='med-{0}'.format(med.med_type.id) if med else None),
        ])
