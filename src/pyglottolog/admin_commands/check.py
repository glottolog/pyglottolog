"""
Check the glottolog data for consistency.
"""
import pathlib
import collections
import dataclasses

import pyglottolog
from pyglottolog.languoids import Reference, LanguoidMapType, Languoid
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
class LanguoidLookup:
    by_id: LanguoidMapType = dataclasses.field(default_factory=dict)
    by_hid: LanguoidMapType = dataclasses.field(default_factory=dict)
    by_name: dict[str, set[Languoid]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(set))
    by_level: collections.Counter[str] = dataclasses.field(default_factory=collections.Counter)
    by_category: collections.Counter[str] = dataclasses.field(default_factory=collections.Counter)

    def update(self, lang, levels, log):
        if lang.id in self.by_id:
            log.error(message(
                lang.id, f'duplicate glottocode\n{self.by_id[lang.id].dir}\n{lang.dir}'))
        self.by_id[lang.id] = lang

        self.by_level.update([lang.level.name])
        if lang.level == levels.language:
            self.by_category.update([lang.category])

        self.by_name[lang.name].add(lang)
        if lang.hid is not None:
            if lang.hid in self.by_hid:
                log.error(message(
                    lang.hid, f'duplicate hid\n{self.by_hid[lang.hid].dir}\n{lang.dir}'))
            else:
                self.by_hid[lang.hid] = lang

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

    refkeys = set()
    for bibfile in args.repos.bibfiles:
        if not args.tree_only:
            bibfile.check(args.log)
        refkeys = refkeys.union(bibfile.keys())

    if args.bib_only:
        return

    iso = args.repos.iso
    iso.log = args.log
    info(iso, 'checking ISO codes')
    info(args.repos, 'checking tree')

    _check_config(args.repos, refkeys, args.log)

    stats = LanguoidLookup()
    for lang in args.repos.languoids():
        stats.update(lang, args.repos.languoid_levels, args.log)
        if iso and lang.iso:
            iso.check_lang(args.repos, lang)

    for lang in stats.by_id.values():
        _check_lang_attrs(lang, args.repos, refkeys, args.log)
        _check_level_consistency(lang, args.repos, stats.by_id, args.log)

    if args.old_languoids:
        if not args.repos.build_path(LanguoidStats.__fname__).exists():
            raise ValueError()  # pragma: no cover
        old_languoid_stats = LanguoidStats.from_json(args.repos)
        old_languoid_stats.check(stats.by_id, args.log)

    iso.check_coverage()

    bookkeeping_gc = args.repos.language_types.bookkeeping.pseudo_family_id
    for name, gcs in sorted(stats.by_name.items()):
        if len(gcs) > 1:
            # duplicate names:
            method = error
            if len([1 for n in gcs if n.level != args.repos.languoid_levels.dialect]) <= 1:
                # at most one of the languoids is not a dialect, just warn
                method = warn  # pragma: no cover
            if len([1 for n in gcs if (not n.lineage) or (n.lineage[0][1] != bookkeeping_gc)]) <= 1:
                # at most one of the languoids is not in bookkeping, just warn
                method = warn  # pragma: no cover
            method(name, 'duplicate name: {0}'.format(  # pylint: disable=C0209
                ', '.join(sorted([f'{n.id} <{n.level.name[0]}>' for n in gcs]))))

    stats.log()


def _check_config(api, refkeys, log):
    for p in pathlib.Path(pyglottolog.__file__).parent.joinpath('config').glob('*.ini'):
        for obj in getattr(api, p.stem).values():
            ref_id = getattr(obj, 'reference_id', None)
            if ref_id and ref_id not in refkeys:
                log.error(message(obj, f'missing reference: {ref_id}'))


def _check_lang_attrs(lang, api, refkeys, log):
    if lang.latitude and not (-90 <= lang.latitude <= 90):
        log.error(message(lang, f'invalid latitude: {lang.latitude}'))
    if lang.longitude and not (-180 <= lang.longitude <= 180):
        log.error(message(lang, f'invalid longitude: {lang.longitude}'))

    assert isinstance(lang.countries, list)
    assert isinstance(lang.macroareas, list)
    assert (lang.timespan is None) or isinstance(lang.timespan, tuple)

    if 'sources' in lang.cfg:
        for ref in Reference.from_list(lang.cfg.getlist('sources', 'glottolog')):
            if ref.key not in refkeys:
                log.error(message(lang, f'missing source: {ref}'))

    for attr in ['classification_comment', 'ethnologue_comment', 'endangerment']:
        obj = getattr(lang, attr)
        if obj:
            obj.check(lang, refkeys, log)

    if not lang.id.startswith('unun9') and lang.id not in api.glottocodes:
        log.error(message(lang, 'unregistered glottocode'))

    for attr in ['level', 'name']:
        if not getattr(lang, attr):
            log.error(message(lang, f'missing {attr}'))  # pragma: no cover

    timespan = lang.timespan
    if timespan and not (
            lang.endangerment and lang.endangerment.status == api.aes_status.extinct):
        log.error(message(lang, 'timespan specified for non-extinct languoid'))  # pragma: no cover


def _check_level_consistency(lang, api, languoids, log):
    ancestors = lang.ancestors_from_nodemap(languoids)
    children = lang.children_from_nodemap(languoids)
    if lang.level == api.languoid_levels.language:
        parent = ancestors[-1] if ancestors else None
        if parent and parent.level != api.languoid_levels.family:  # pragma: no cover
            log.error(message(lang, f'invalid nesting of language under {parent.level}'))
        for child in children:
            if child.level != api.languoid_levels.dialect:  # pragma: no cover
                log.error(message(child, f'invalid nesting of {child.level} under language'))
    elif lang.level == api.languoid_levels.family:
        for d in lang.dir.iterdir():
            if d.is_dir():
                break
        else:
            log.error(message(lang, 'family without children'))  # pragma: no cover
