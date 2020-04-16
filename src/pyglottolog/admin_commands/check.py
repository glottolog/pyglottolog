"""
Check the glottolog data for consistency.
"""
import collections

from pyglottolog.languoids import Reference
from pyglottolog.util import message
import pyglottolog.iso


def register(parser):
    parser.add_argument(
        '--bib-only',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--tree-only',
        action='store_true',
        default=False,
    )


def run(args):
    def error(obj, msg):
        args.log.error(message(obj, msg))

    def warn(obj, msg):
        args.log.warning(message(obj, msg))

    def info(obj, msg):
        args.log.info(message(obj, msg))

    if not args.tree_only:
        for bibfile in args.repos.bibfiles:
            bibfile.check(args.log)

    if args.bib_only:
        return

    refkeys = set()
    for bibfile in args.repos.bibfiles:
        refkeys = refkeys.union(bibfile.keys())

    iso = args.repos.iso
    info(iso, 'checking ISO codes')
    info(args.repos, 'checking tree')
    by_level = collections.Counter()
    by_category = collections.Counter()
    iso_in_gl, languoids, iso_splits, hid = {}, {}, [], {}
    names = collections.defaultdict(set)

    for attr in args.repos.__config__:
        for obj in getattr(args.repos, attr).values():
            ref_id = getattr(obj, 'reference_id', None)
            if ref_id and ref_id not in refkeys:
                error(obj, 'missing reference: {0}'.format(ref_id))

    for lang in args.repos.languoids():
        # duplicate glottocodes:
        if lang.id in languoids:
            error(
                lang.id,
                'duplicate glottocode\n{0}\n{1}'.format(languoids[lang.id].dir, lang.dir))
        languoids[lang.id] = lang

    for lang in languoids.values():
        ancestors = lang.ancestors_from_nodemap(languoids)
        children = lang.children_from_nodemap(languoids)

        if lang.latitude and not (-90 <= lang.latitude <= 90):
            error(lang, 'invalid latitude: {0}'.format(lang.latitude))
        if lang.longitude and not (-180 <= lang.longitude <= 180):
            error(lang, 'invalid longitude: {0}'.format(lang.longitude))

        assert isinstance(lang.countries, list)
        assert isinstance(lang.macroareas, list)
        assert (lang.timespan is None) or isinstance(lang.timespan, tuple)

        if 'sources' in lang.cfg:
            for ref in Reference.from_list(lang.cfg.getlist('sources', 'glottolog')):
                if ref.key not in refkeys:
                    error(lang, 'missing source: {0}'.format(ref))

        for attr in ['classification_comment', 'ethnologue_comment']:
            obj = getattr(lang, attr)
            if obj:
                obj.check(lang, refkeys, args.log)

        names[lang.name].add(lang)
        by_level.update([lang.level.name])
        if lang.level == args.repos.languoid_levels.language:
            by_category.update([lang.category])

        if iso and lang.iso:
            if lang.iso not in iso:
                warn(lang, 'invalid ISO-639-3 code [%s]' % lang.iso)
            else:
                isocode = iso[lang.iso]
                if lang.iso in iso_in_gl:
                    error(
                        isocode,
                        'duplicate: {0}, {1}'.format(
                            iso_in_gl[lang.iso].id, lang.id))  # pragma: no cover
                iso_in_gl[lang.iso] = lang
                isocheck = pyglottolog.iso.check_lang(
                    args.repos, isocode, lang, iso_splits=iso_splits)
                if isocheck:
                    level, lang, msg = isocheck
                    dict(info=info, warn=warn)[level](lang, msg)

        if lang.hid is not None:
            if lang.hid in hid:
                error(
                    lang.hid,
                    'duplicate hid\n{0}\n{1}'.format(languoids[hid[lang.hid]].dir, lang.dir))
            else:
                hid[lang.hid] = lang.id

        if not lang.id.startswith('unun9') and lang.id not in args.repos.glottocodes:
            error(lang, 'unregistered glottocode')
        for attr in ['level', 'name']:
            if not getattr(lang, attr):
                error(lang, 'missing %s' % attr)  # pragma: no cover
        if lang.level == args.repos.languoid_levels.language:
            parent = ancestors[-1] if ancestors else None
            if parent and parent.level != args.repos.languoid_levels.family:  # pragma: no cover
                error(lang, 'invalid nesting of language under {0}'.format(parent.level))
            for child in children:
                if child.level != args.repos.languoid_levels.dialect:  # pragma: no cover
                    error(child,
                          'invalid nesting of {0} under language'.format(child.level))
        elif lang.level == args.repos.languoid_levels.family:
            for d in lang.dir.iterdir():
                if d.is_dir():
                    break
            else:
                error(lang, 'family without children')  # pragma: no cover

        try:
            endangerment = lang.endangerment
            if endangerment and endangerment.source and endangerment.source.reference_id:
                ref = endangerment.source.reference_id
                if ref not in refkeys:  # pragma: no cover
                    error(lang, 'endangerment: invalid ref {0}'.format(ref))
        except (ValueError, KeyError) as e:  # pragma: no cover
            error(lang, 'endangerment: {0}: {1}'.format(e.__class__.__name__, str(e)))

    if iso:
        for level, obj, msg in pyglottolog.iso.check_coverage(iso, iso_in_gl, iso_splits):
            dict(info=info, warn=warn)[level](obj, msg)  # pragma: no cover

    bookkeeping_gc = args.repos.language_types.bookkeeping.pseudo_family_id
    for name, gcs in sorted(names.items()):
        if len(gcs) > 1:
            # duplicate names:
            method = error
            if len([1 for n in gcs if n.level != args.repos.languoid_levels.dialect]) <= 1:
                # at most one of the languoids is not a dialect, just warn
                method = warn  # pragma: no cover
            if len([1 for n in gcs
                    if (not n.lineage) or (n.lineage[0][1] != bookkeeping_gc)]) <= 1:
                # at most one of the languoids is not in bookkeping, just warn
                method = warn  # pragma: no cover
            method(name, 'duplicate name: {0}'.format(', '.join(sorted(
                ['{0} <{1}>'.format(n.id, n.level.name[0]) for n in gcs]))))

    def log_counter(counter, name):
        msg = [name + ':']
        maxl = max([len(k) for k in counter.keys()]) + 1
        for k, l in counter.most_common():
            msg.append(('{0:<%s} {1:>8,}' % maxl).format(k + ':', l))
        msg.append(('{0:<%s} {1:>8,}' % maxl).format('', sum(list(counter.values()))))
        print('\n'.join(msg))

    log_counter(by_level, 'Languoids by level')
    log_counter(by_category, 'Languages by category')
    return by_level
