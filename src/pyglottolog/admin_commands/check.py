"""
Check the glottolog data for consistency.
"""
import pathlib
import collections
import dataclasses

import pyglottolog
from pyglottolog.languoids import Reference
from pyglottolog.util import message
from pyglottolog.cli_util import LanguoidStats
import pyglottolog.iso


def register(parser):  # pylint: disable=C0116
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
    parser.add_argument(
        '--old-languoids',
        action='store_true',
        default=False,
    )


@dataclasses.dataclass
class Stats:
    by_level: collections.Counter[str] = dataclasses.field(default_factory=collections.Counter)
    by_category: collections.Counter[str] = dataclasses.field(default_factory=collections.Counter)

    def update(self, lang, levels):
        self.by_level.update([lang.level.name])
        if lang.level == levels.language:
            self.by_category.update([lang.category])

    @staticmethod
    def _log_counter(counter, name):
        msg = [name + ':']
        maxl = max([len(k) for k in counter.keys()]) + 1
        for k, l in counter.most_common():
            msg.append(('{0:<%s} {1:>8,}' % maxl).format(k + ':', l))
        msg.append(('{0:<%s} {1:>8,}' % maxl).format('', sum(list(counter.values()))))
        print('\n'.join(msg))

    def log(self):
        self._log_counter(self.by_level, 'Languoids by level')
        self._log_counter(self.by_category, 'Languages by category')


def run(args):  # pylint: disable=C0116
    def error(obj, msg):
        args.log.error(message(obj, msg))

    def warn(obj, msg):  # pragma: no cover
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
    iso.log = args.log
    info(iso, 'checking ISO codes')
    info(args.repos, 'checking tree')

    stats = Stats()
    languoids, hid = {}, {}
    names = collections.defaultdict(set)

    for p in pathlib.Path(pyglottolog.__file__).parent.joinpath('config').glob('*.ini'):
        for obj in getattr(args.repos, p.stem).values():
            ref_id = getattr(obj, 'reference_id', None)
            if ref_id and ref_id not in refkeys:
                error(obj, f'missing reference: {ref_id}')

    if args.old_languoids and not args.repos.build_path('languoids.json').exists():
        raise ValueError()  # pragma: no cover
    old_languoid_stats = LanguoidStats.from_json(args.repos)
    languoids = old_languoid_stats.check(args.repos, args.log)

    for lang in languoids.values():
        ancestors = lang.ancestors_from_nodemap(languoids)
        children = lang.children_from_nodemap(languoids)

        if lang.latitude and not (-90 <= lang.latitude <= 90):
            error(lang, f'invalid latitude: {lang.latitude}')
        if lang.longitude and not (-180 <= lang.longitude <= 180):
            error(lang, f'invalid longitude: {lang.longitude}')

        assert isinstance(lang.countries, list)
        assert isinstance(lang.macroareas, list)
        assert (lang.timespan is None) or isinstance(lang.timespan, tuple)

        if 'sources' in lang.cfg:
            for ref in Reference.from_list(lang.cfg.getlist('sources', 'glottolog')):
                if ref.key not in refkeys:
                    error(lang, f'missing source: {ref}')

        for attr in ['classification_comment', 'ethnologue_comment']:
            obj = getattr(lang, attr)
            if obj:
                obj.check(lang, refkeys, args.log)

        names[lang.name].add(lang)
        stats.update(lang, args.repos.languoid_levels)

        if iso and lang.iso:
            iso.check_lang(args.repos, lang)

        if lang.hid is not None:
            if lang.hid in hid:
                error(lang.hid, f'duplicate hid\n{languoids[hid[lang.hid]].dir}\n{lang.dir}')
            else:
                hid[lang.hid] = lang.id

        if not lang.id.startswith('unun9') and lang.id not in args.repos.glottocodes:
            error(lang, 'unregistered glottocode')
        for attr in ['level', 'name']:
            if not getattr(lang, attr):
                error(lang, f'missing {attr}')  # pragma: no cover
        if lang.level == args.repos.languoid_levels.language:
            parent = ancestors[-1] if ancestors else None
            if parent and parent.level != args.repos.languoid_levels.family:  # pragma: no cover
                error(lang, f'invalid nesting of language under {parent.level}')
            for child in children:
                if child.level != args.repos.languoid_levels.dialect:  # pragma: no cover
                    error(child, f'invalid nesting of {child.level} under language')
        elif lang.level == args.repos.languoid_levels.family:
            for d in lang.dir.iterdir():
                if d.is_dir():
                    break
            else:
                error(lang, 'family without children')  # pragma: no cover

        if lang.endangerment:
            lang.endangerment.check(lang, refkeys, args.log)

        timespan = lang.timespan
        if timespan and not (
                lang.endangerment and lang.endangerment.status == args.repos.aes_status.extinct):
            error(lang, 'timespan specified for non-extinct languoid')  # pragma: no cover

    iso.check_coverage()

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

    stats.log()
