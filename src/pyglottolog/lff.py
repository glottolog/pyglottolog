"""
Convert between Glottolog's Languoid trees and the lff format.

Abkhaz-Adyge [abkh1242] aaa
    Ubykh [ubyk1235]uby
Abkhaz-Adyge [abkh1242] aaa; Abkhaz-Abaza [abkh1243]
    Abaza [abaz1241]abq
    Abkhazian [abkh1244]abk
"""
import re
import os
import shutil
import logging
import pathlib
import operator
import collections
from collections.abc import Sequence, Generator
import dataclasses
from typing import TYPE_CHECKING, Optional

from clldutils.path import readlines

from pyglottolog.config import LanguoidLevel
from .languoids import Languoid, Glottocode
from .util import PathType

if TYPE_CHECKING:
    from pyglottolog import Glottolog

ISOLATE_ID = '-isolate-'
LINEAGE_SEP = ';'
NAME_AND_ID_PATTERN = re.compile(
    r'(?P<name>[^\[;]+)'
    r'(\[(?P<gc>(' + Glottocode.regex + ')|' + ISOLATE_ID + r')?])\s*'
    r'(?P<hid>[a-z]{3}|NOCODE_[^;]+)?$')
LineageType = tuple[str, str, str, str]
NameGcIsoType = tuple[str, str, str]


@dataclasses.dataclass
class LffLanguoid:
    """
    In lff, the core languoid data and the classification are read from different lines.
    Here, we combine this info.
    """
    languoid: Languoid
    lineage: list[LineageType]


@dataclasses.dataclass
class Registry:
    """Registry, handing out new Glottocodes if necessary."""
    api: 'Glottolog'
    new: dict[tuple[str, LanguoidLevel], Glottocode] = dataclasses.field(default_factory=dict)

    def get(self, name: str, level: LanguoidLevel) -> str:
        """Get a (possibly newly minted) Glottocode from the registry."""
        glottocode = self.new.get((name, level))
        if not glottocode:  # Mint a new Glottocode.
            glottocode = self.new[name, level] = self.api.glottocodes.new(name)
        return glottocode


@dataclasses.dataclass
class OldTree:
    """We store the old Languoids from the tree, to be updated with new data read from lff."""
    tree: dict[str, Languoid]

    def updated_language(self, lg: Languoid, log: logging.Logger) -> Languoid:
        """Update a Languoid object from the old tree with new data and return it."""
        old_lang = self.tree[lg.id]
        if old_lang.level != lg.level:
            log.info('%s from %s to %s', old_lang, old_lang.level, lg.level)
            old_lang.level = lg.level
        if old_lang.name != lg.name:
            old_lang.add_name(old_lang.name)
            old_lang.name = lg.name
        if old_lang.iso != lg.iso:
            old_lang.iso = lg.iso
        if lg.hid and old_lang.hid != lg.hid:
            old_lang.hid = lg.hid
        return old_lang

    def updated_group(self, id_, name, level, log) -> Languoid:
        """Update a family-level Languoid from the old tree with new data and return it."""
        group = self.tree[id_]
        if group.level != level:
            log.info('%s from %s to %s', group, group.level, level)
            group.level = level
        if name != group.name:
            # rename a subgroup!
            group.add_name(group.name)
            group.name = name
        return group


def parse_languoid(s: str, log) -> NameGcIsoType:
    """
    >>> parse_languoid('Sprache [abcd1234] iso', None)
    ('Sprache', 'abcd1234', 'iso')
    """
    match = NAME_AND_ID_PATTERN.match(s.strip())
    if not match or not match.group('name').strip():
        log.error('Invalid languoid spec: %s', s)
        raise ValueError()
    return match.group('name').strip(), match.group('gc'), match.group('hid')


def rmtree(d: PathType):
    """More performant way to remove large directory structures."""
    d = str(d)
    for path in (os.path.join(d, f) for f in os.listdir(d)):
        if os.path.isdir(path):
            rmtree(path)
        else:
            os.unlink(path)
    os.rmdir(d)


def _iter_lineage(  # pylint: disable=R0913,R0917
        path,
        level,
        llevels,
        lname,
        glottocode,
        registry,
        log,
) -> Generator[LineageType, None, None]:
    for i, (name, id_, hid) in enumerate(path):
        if id_ == ISOLATE_ID:
            if i != 0 or len(path) != 1:
                log.error(
                    'invalid classification line for languoid: %s [%s]', lname, glottocode)
                raise ValueError('invalid isolate line')
            break
        _level = llevels.family
        if level == llevels.dialect:
            _level = llevels.language if i == 0 else llevels.dialect

        if not id_:
            id_ = registry.get(name, _level)

        yield (name, id_, _level, hid)


def languoid(  # pylint: disable=R0913,R0917
        api: 'Glottolog',
        log: logging.Logger,
        registry: Registry,
        path: Sequence[tuple[str, str, str]],
        name_gc_iso: NameGcIsoType,
        level: LanguoidLevel,
) -> LffLanguoid:
    """
    Instantiate a Languoid from lff.
    """
    lname, glottocode, isocode = name_gc_iso
    if not glottocode:
        glottocode = registry.get(lname, level)

    lineage: list[LineageType] = []
    if path:
        lineage = list(_iter_lineage(
            path,
            level,
            api.languoid_levels,
            lname,
            glottocode,
            registry, log
        ))

    lang = Languoid.from_name_id_level(
        api.tree, lname, glottocode, level, lineage=[(r[0], r[1], r[2]) for r in lineage], _api=api)
    if (isocode in api.iso) or (isocode is None):
        lang.iso = isocode
    lang.hid = isocode
    return LffLanguoid(lang, lineage)


def read_lff(
        api: 'Glottolog',
        log: logging.Logger,
        new: Registry,
        level: LanguoidLevel,
        fname: Optional[PathType] = None,
) -> Generator[LffLanguoid, None, None]:
    """Yield languoids as read from a lff file."""
    assert level in [api.languoid_levels.language, api.languoid_levels.dialect]
    log.info('reading %ss from %s', level.name, fname)

    fname = fname or api.build_path(f'{level.name[0]}ff.txt')

    path = None
    for line in readlines(fname):
        line = line.rstrip()
        if line.startswith('#') or not line.strip():
            # ignore comments or empty lines
            continue

        if re.match(r'\s', line):
            # leading whitespace => a language/dialect spec.
            if path is None:
                raise ValueError('language line without classification line')
            name_gc_iso = parse_languoid(line.strip(), log)
            yield languoid(api, log, new, path, name_gc_iso, level)
        else:
            path = [parse_languoid(s.strip(), log) for s in line.split(LINEAGE_SEP)]


def lang2tree(
        api: 'Glottolog',
        log: logging.Logger,
        lg: LffLanguoid,
        out: pathlib.Path,
        old_tree: OldTree,
):
    """Update directories/files in the Glottolog languoids tree for an item from lff."""
    groupdir = out

    for spec in lg.lineage:
        hid = -1
        name, id_, level = spec[:3]
        if len(spec) == 4:
            hid = spec[3]

        groupdir = groupdir.joinpath(id_)
        if not groupdir.exists():
            groupdir.mkdir()
            if id_ in old_tree.tree:
                group = old_tree.updated_group(id_, name, level, log)
            else:
                group = Languoid.from_name_id_level(api.tree, name, id_, level, _api=api)

            if hid != -1:
                if (hid in api.iso or hid is None) and group.iso != hid:
                    group.iso = hid
                if hid != group.hid:
                    group.hid = hid
            group.write_info(groupdir)

    langdir = groupdir.joinpath(lg.languoid.id)
    langdir.mkdir()

    if lg.languoid.id in old_tree.tree:
        lg.languoid = old_tree.updated_language(lg.languoid, log)
    lg.languoid.write_info(langdir)


@dataclasses.dataclass
class ConsistencyChecker:
    """
    In lff, classification info may be redundant.
    Thus, upon reading we make sure it is consistent.
    """
    languoids: dict[str, tuple[str, str, str]] = dataclasses.field(default_factory=dict)

    def checked(self, lg: LffLanguoid, log) -> LffLanguoid:
        """Check whether classification info across branches is consistent."""
        assert lg.languoid.id not in self.languoids
        for n, gc, _level, hid in lg.lineage:
            if gc in self.languoids:
                if self.languoids[gc] != (n, _level, hid):
                    log.error('%s: %s vs %s', gc, self.languoids[gc], (n, _level, hid))
                    raise ValueError('inconsistent languoid data')
            else:
                self.languoids[gc] = (n, _level, hid)
        self.languoids[lg.languoid.id] = (
            lg.languoid.name, lg.languoid.level, lg.languoid.iso or lg.languoid.hid)
        return lg


def lff2tree(api, log=logging.getLogger(__name__)):
    """
    - get mapping glottocode -> Languoid from old tree
    - assemble new directory tree
      - for each path component in lff/dff:
        - create new dir
        - copy info file from old tree (possibly updating the name) or
        - create info file
      - for each language/dialect in lff/dff:
        - create new dir
        - copy info file from old tree (possibly updating the name) or
        - create info file
    - rm old tree
    - copy new tree
    """
    old_tree: OldTree = OldTree({lang.id: lang for lang in api.languoids()})

    if api.tree.exists():
        if api.build_path('tree').exists():
            try:
                rmtree(api.build_path('tree'))
            except Exception:  # pragma: no cover  # pylint: disable=W0718
                pass
            if api.build_path('tree').exists():  # pragma: no cover
                raise ValueError(f'please remove {api.build_path("tree")} before proceeding')
        # move the old tree out of the way
        shutil.move(api.tree, api.build_path('tree'))
    api.tree.mkdir()

    checker = ConsistencyChecker()
    new = Registry(api)
    languages = {}
    for lg in read_lff(api, log, new, api.languoid_levels.language, api.build_path('lff.txt')):
        languages[lg.languoid.id] = checker.checked(lg, log)
        lang2tree(api, log, lg, api.tree, old_tree)

    for lg in read_lff(api, log, new, api.languoid_levels.dialect, api.build_path('dff.txt')):
        lg = checker.checked(lg, log)
        if not lg.lineage or lg.lineage[0][1] not in languages:
            log.error(
                'missing language in dff: %s [%s]',
                lg.lineage[0][0], lg.lineage[0][1])
            raise ValueError('invalid language referenced')

        lg.lineage = languages[lg.lineage[0][1]].lineage + lg.lineage
        lang2tree(api, log, lg, api.tree, old_tree)

    duplicates = False
    for name, getter in [('name', operator.itemgetter(0)), ('hid', operator.itemgetter(2))]:
        count = collections.Counter(getter(spec) for spec in checker.languoids.values())
        for thing, n in count.most_common():
            if thing is None:
                continue
            if n < 2:
                break
            log.error('duplicate %s: %s (%s)', name, thing, n)
            duplicates = True
    if duplicates:
        raise ValueError('duplicates found')


def format_comp(lang, gc=None) -> str:
    """Tree nodes in lff are formatted as <name> [<glottocode>] <iso-or-hid>"""
    res = f'{lang.name} [{gc or lang.id}]'
    if lang.iso:
        res += f' {lang.iso}'
    elif lang.hid:
        res += f' {lang.hid}'
    return res


def format_language(lang) -> str:
    """Language (or dialect) lines in lff are indented."""
    return f'    {format_comp(lang)}'


def format_classification(
        api: 'Glottolog',
        lang: Languoid,
        parents: dict[str, Languoid]) -> str:
    """<languoid>; <languoid> ..."""
    if not lang.lineage:
        return format_comp(lang, gc=ISOLATE_ID)
    comps = []
    for _, gc, _ in lang.lineage:
        a = parents[gc]
        if lang.level == api.languoid_levels.language or \
                (lang.level == api.languoid_levels.dialect and  # noqa: W504
                 a.level != api.languoid_levels.family):
            comps.append(format_comp(a))
    return (LINEAGE_SEP + ' ').join(comps)


def tree2lff(
        api: 'Glottolog',
        log: logging.Logger = logging.getLogger(__name__),
):
    """Format a languoid tree in the lff format."""
    languoids: dict[LanguoidLevel, dict[str, list[str]]] = {
        api.languoid_levels.dialect: collections.defaultdict(list),
        api.languoid_levels.language: collections.defaultdict(list)}

    # We collect a mapping from Glottocode to Languoid while already formatting the classifications.
    # This is possible, because `api.languoids` returns a Languoid only after all its parents have
    # been returned.
    agg = {}
    for lang in api.languoids():
        agg[lang.id] = lang
        if lang.level in languoids:
            languoids[lang.level][format_classification(api, lang, agg)].append(
                format_language(lang))

    for level, languages in languoids.items():
        ff = api.build_path(f'{level.name[0]}ff.txt')
        with ff.open('w', encoding='utf8') as fp:
            fp.write('# -*- coding: utf-8 -*-\n')
            for path in sorted(languages):
                fp.write(path + '\n')
                for lang in sorted(languages[path]):
                    fp.write(lang + '\n')
        log.info('%ss written to %s', level.name, ff.as_posix())
