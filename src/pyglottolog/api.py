"""
Programmatic access to Glottolog data.
"""
import re
import types
from typing import Union, Optional, TypedDict
import pathlib
import functools
import contextlib
import collections
from collections.abc import Generator

from clldutils.path import walk, git_describe
from clldutils.apilib import API
import clldutils.iso_639_3
import pycountry
from termcolor import colored
from tqdm import tqdm

from . import util
from . import languoids as lls
from . import references
from . import config
from .languoids import models

__all__ = ['Glottolog']

LanguoidOrCode = Union[str, lls.Languoid]
ISO_CODE_PATTERN = re.compile('[a-z]{3}$')


class TriggerDict(TypedDict):
    """Triggers by bibfile field name."""
    inlg: list[util.Trigger]
    lgcode: list[util.Trigger]


class Cache(dict):
    """
    Since reading languoid metadata from disk is expensive, we provide a mechanism to cache them.
    """
    def __init__(self):
        super().__init__()
        self._lineage = {}

    def __bool__(self):
        return True

    def add(self, directory: pathlib.Path, api: 'Glottolog') -> lls.Languoid:
        """Add a languoid specified by directory in the Glottolog tree to the cache."""
        if directory.name not in self:
            lang = lls.Languoid.from_dir(directory, nodes=self._lineage, _api=api)
            self._lineage[lang.id] = (lang.name, lang.id, lang.level)
            self[lang.id] = lang
            if lang.iso:
                self[lang.iso] = lang
        else:
            lang = self[directory.name]
        return lang


class Glottolog(API):  # pylint: disable=too-many-public-methods
    """
    API to access Glottolog data

    This class provides (read and write) access to a local copy of the Glottolog data, which can
    be obtained as explained in the `README <https://github.com/glottolog/pyglottolog#install>`_
    """
    countries = [models.Country(c.alpha_2, c.name) for c in pycountry.countries]

    def __init__(self, repos='.', *, cache: bool = False):
        """
        :param repos: Path to a copy of `<https://github.com/glottolog/glottolog>`_
        :param cache: Indicate whether to cache `Languoid` objects or not. If `True`, the API must \
        be used read-only.
        """
        API.__init__(self, repos=repos)
        #: Absolute path to the copy of the data repository:
        self.repos: pathlib.Path = pathlib.Path.cwd() / self.repos
        #: Absolute path to the `tree` directory in the repos.
        self.tree: pathlib.Path = self.repos / 'languoids' / 'tree'
        if not self.tree.exists():
            raise ValueError(f'repos dir {self.repos} missing tree dir: {self.tree}')
        if not self.repos.joinpath('references').exists():
            raise ValueError(f'repos dir {self.repos} missing references subdir')
        self.cache: lls.LanguoidMapType = Cache() if cache else None

    def __str__(self):
        return f'<Glottolog repos {git_describe(self.repos)} at {self.repos}>'

    def describe(self) -> str:  # pylint: disable=C0116
        return git_describe(self.repos)

    def references_path(self, *comps: str) -> pathlib.Path:
        """
        Path within the `references` directory of the repos.
        """
        return self.repos.joinpath('references', *comps)

    def languoids_path(self, *comps) -> pathlib.Path:
        """
        Path within the `languoids` directory of the repos.
        """
        return self.repos.joinpath('languoids', *comps)

    def build_path(self, *comps: str) -> pathlib.Path:  # pylint: disable=C0116
        build_dir = self.repos.joinpath('build')
        if not build_dir.exists():
            build_dir.mkdir()  # pragma: no cover
        return build_dir.joinpath(*comps)

    @contextlib.contextmanager
    def cache_dir(self, name: str):  # pylint: disable=C0116
        d = self.build_path(name)
        if not d.exists():
            d.mkdir()
        yield d

    def _cfg(self, name, cls=None):
        return config.Config.from_ini(
            self.path('config', name + '.ini'), object_class=cls or types.SimpleNamespace)

    @functools.cached_property
    def aes_status(self) -> dict[str, config.AES]:
        """
        :rtype: mapping with :class:`config.AES` values.
        """
        return self._cfg('aes_status', cls=config.AES)

    @functools.cached_property
    def aes_sources(self) -> dict[str, config.AESSource]:
        """
        :rtype: mapping with :class:`config.AESSource` values
        """
        return self._cfg('aes_sources', cls=config.AESSource)

    @functools.cached_property
    def document_types(self) -> dict[str, config.DocumentType]:
        """
        :rtype: mapping with :class:`config.DocumentType` values
        """
        return self._cfg('document_types', cls=config.DocumentType)

    @functools.cached_property
    def med_types(self) -> dict[str, config.MEDType]:
        """
        :rtype: mapping with :class:`config.MEDType` values
        """
        return self._cfg('med_types', cls=config.MEDType)

    @functools.cached_property
    def macroareas(self) -> dict[str, config.Macroarea]:
        """
        :rtype: mapping with :class:`config.Macroarea` values
        """
        return self._cfg('macroareas', cls=config.Macroarea)

    @functools.cached_property
    def language_types(self) -> dict[str, config.LanguageType]:
        """
        :rtype: mapping with :class:`config.LanguageType` values
        """
        return self._cfg('language_types', cls=config.LanguageType)

    @functools.cached_property
    def languoid_levels(self) -> dict[str, config.LanguoidLevel]:
        """
        :rtype: mapping with :class:`config.LanguoidLevel` values
        """
        return self._cfg('languoid_levels', cls=config.LanguoidLevel)

    @functools.cached_property
    def editors(self) -> dict[str, config.Editors]:
        """
        Metadata about editors of Glottolog

        :rtype: mapping with :class:`config.Generic` values
        """
        return self._cfg('editors', cls=config.Editors)

    @functools.cached_property
    def publication(self) -> dict[str, str]:
        """
        Metadata about the Glottolog publication

        :rtype: mapping with :class:`config.Generic` values
        """
        return self._cfg('publication')

    @functools.cached_property
    def iso(self) -> clldutils.iso_639_3.ISO:
        """
        :return: `clldutils.iso_639_3.ISO` instance, fed with the data of the latest \
        ISO code table zip found in the `build` directory.
        """
        return util.get_iso(self.build_path())

    @functools.cached_property
    def _tree_dirs(self):
        return list(walk(self.tree, mode='dirs'))

    @property
    def glottocodes(self) -> models.Glottocodes:
        """
        Registry of Glottocodes.
        """
        return models.Glottocodes(self.languoids_path('glottocodes.json'))

    def languoid(self, id_: LanguoidOrCode) -> Optional[lls.Languoid]:
        """
        Retrieve a languoid specified by language code.

        :param id_: Glottocode or ISO code.
        """
        if isinstance(id_, lls.Languoid):
            return id_

        if self.cache and id_ in self.cache:
            return self.cache[id_]

        if ISO_CODE_PATTERN.match(id_):
            for d in self._tree_dirs if self.cache else walk(self.tree, mode='dirs'):
                if self.cache:
                    l_ = self.cache.add(d, self)
                else:
                    l_ = lls.Languoid.from_dir(d, _api=self)
                if l_.iso_code == id_:
                    return l_
        else:
            for d in self._tree_dirs if self.cache else walk(self.tree, mode='dirs'):
                l_ = None
                if self.cache:
                    # If we cache Languoids, we might as well instantiate the ones we traverse:
                    l_ = self.cache.add(d, self)
                if d.name == id_:
                    if self.cache:
                        return l_
                    return lls.Languoid.from_dir(d, _api=self)
        return None

    def languoids(
            self,
            ids: set = None,
            maxlevel: Union[int, config.LanguoidLevel, str] = None,
            exclude_pseudo_families: bool = False
    ) -> Generator[lls.Languoid, None, None]:
        """
        Yields languoid objects.

        :param ids: `set` of Glottocodes to limit the result to. This is useful to increase \
        performance, since INI file reading can be skipped for languoids not listed.
        :param maxlevel: Numeric maximal nesting depth of languoids, or Languoid.level.
        :param exclude_pseudo_families: Flag signaling whether to exclude pseud families, \
        i.e. languoids from non-genealogical trees.
        """
        is_max_level_int = isinstance(maxlevel, int)
        # Non-numeric levels are interpreted as `Languoid.level` descriptors.
        if not is_max_level_int:
            maxlevel = self.languoid_levels.get(maxlevel or 'dialect')

        # Since we traverse the tree topdown, we can cache a mapping of Languoid.id to triples
        # (name, id, level) for populating `Languoid.lineage`.
        nodes = {}
        for d in self._tree_dirs if self.cache else walk(self.tree, mode='dirs'):
            if ids is None or d.name in ids:
                if self.cache:
                    lang = self.cache.add(d, self)
                else:
                    lang = lls.Languoid.from_dir(d, nodes=nodes, _api=self)
                if (is_max_level_int and len(lang.lineage) <= maxlevel) \
                        or ((not is_max_level_int) and lang.level <= maxlevel):
                    if (not exclude_pseudo_families) or not lang.category.startswith('Pseudo'):
                        yield lang

    def languoids_by_code(self, nodes: Optional[lls.LanguoidMapType] = None) -> lls.LanguoidMapType:
        """
        Returns a `dict` mapping the three major language code schemes
        (Glottocode, ISO code, and Harald's NOCODE_s) to Languoid objects.
        """
        res = {}
        for lang in (self.languoids() if nodes is None else nodes.values()):
            res[lang.id] = lang
            if lang.hid:
                res[lang.hid] = lang
            if lang.iso:
                res[lang.iso] = lang
        return res

    def ascii_tree(self, start: LanguoidOrCode, maxlevel=None):
        """
        Prints an ASCII representation of the languoid tree starting at `start` to `stdout`.
        """
        _ascii_node(
            self.languoid(start),
            0,
            True,
            self.languoid_levels.get(maxlevel, maxlevel) if maxlevel else None,
            '',
            self.languoid_levels)

    def newick_tree(
            self,
            start: Optional[LanguoidOrCode] = None,
            template: str = None,
            nodes: Optional[lls.LanguoidMapType] = None,
            maxlevel: Union[int, config.LanguoidLevel] = None
    ) -> str:
        """
        Returns the Newick representation of a (set of) Glottolog classification tree(s).

        :param start: Root languoid of the tree (or `None` to return the complete classification).
        :param template: Python format string accepting the `Languoid` instance as single \
        variable named `l`, used to format node labels.
        """
        template = template or lls.Languoid._newick_default_template  # pylint: disable=W0212
        if start:
            return self.languoid(start).newick_node(
                template=template, nodes=nodes, maxlevel=maxlevel, level=1).newick + ';'
        if nodes is None:
            nodes = collections.OrderedDict((lang.id, lang) for lang in self.languoids())
        trees = []
        for lang in nodes.values():
            if not lang.lineage and not lang.category.startswith('Pseudo '):
                ns = lang.newick_node(
                    nodes=nodes, template=template, maxlevel=maxlevel, level=1).newick
                if lang.level == self.languoid_levels.language:
                    # An isolate: we wrap it in a pseudo-family with the same name and ID.
                    fam = lls.Languoid.from_name_id_level(
                        lang.dir.parent, lang.name, lang.id, 'family', _api=self)
                    ns = f'({ns}){template.format(l=fam)}:1'  # noqa: E741
                trees.append(f'{ns};')
        return '\n'.join(trees)

    @functools.cached_property
    def bibfiles(self) -> references.BibFiles:
        """
        Access reference data by BibFile.

        :rtype: :class:`references.BibFiles`
        """
        return references.BibFiles.from_path(self.references_path(), api=self)

    def refs_by_languoid(
            self,
            *bibfiles: Union[references.BibFile, str],
            nodes: Optional[lls.LanguoidMapType] = None,
    ) -> tuple[dict[lls.Glottocode, list[references.Entry]], dict[str, references.Entry]]:
        """
        Get references from bibfiles keyed by associated Glottocodes.
        """
        if bibfiles:
            bibfiles = [
                bib if isinstance(bib, references.BibFile) else self.bibfiles[bib]
                for bib in bibfiles]
        else:
            bibfiles = self.bibfiles

        all_: dict[str, references.Entry] = {}
        languoids_by_code = self.languoids_by_code(
            nodes or {lang.id: lang for lang in self.languoids()})
        res: dict[lls.Glottocode, list[references.Entry]] = collections.defaultdict(list)
        for bib in tqdm(bibfiles):
            for entry in bib.iterentries():
                all_[entry.id] = entry
                for lang in entry.languoids(languoids_by_code)[0]:
                    res[lang.id].append(entry)
        return res, all_

    @functools.cached_property
    def hhtypes(self):  # pylint: disable=C0116
        # Note: The file `hhtype.ini` does not exist anymore. This is fixed in HHTypes, when
        # calling `config.get_ini`. Only used when compiling monster.bib.
        return references.HHTypes(self.references_path('hhtype.ini'))

    @functools.cached_property
    def triggers(self) -> TriggerDict:  # pylint: disable=C0116
        res: TriggerDict = {'inlg': [], 'lgcode': []}
        for lang in self.languoids():
            for type_ in TriggerDict.__annotations__:
                if lang.cfg.has_option('triggers', type_):
                    label = f'{lang.name} [{lang.hid or lang.id}]'
                    res[type_].extend([util.Trigger(type_, label, text)
                                       for text in lang.cfg.getlist('triggers', type_)])
        return res

    @functools.cached_property
    def macroarea_map(self) -> dict[str, str]:
        """Maps language codes (Glottocode, ISO code, hid) to the first macroarea name."""
        res = {}
        for lang in self.languoids():
            ma = lang.macroareas[0].name if lang.macroareas else ''
            res[lang.id] = ma
            if lang.iso:
                res[lang.iso] = ma
            if lang.hid:
                res[lang.hid] = ma
        return res

    @property
    def current_editors(self) -> list[config.Editors]:  # pylint: disable=C0116
        return sorted([e for e in self.editors.values() if e.current], key=lambda e: int(e.ord))


def _ascii_node(n, level, last, maxlevel, prefix, levels):  # pylint: disable=R0913,R0917
    nlevel = levels.get(n.level)
    if maxlevel:
        if (isinstance(maxlevel, config.LanguoidLevel) and nlevel > maxlevel) or \
                (not isinstance(maxlevel, config.LanguoidLevel) and level > maxlevel):
            return
    s = '\u2514' if last else '\u251c'
    s += '\u2500 '

    if not level:
        for i, node in enumerate(n.ancestors):
            util.sprint('{0}{1}{2} [{3}]', prefix, s if i else '', node.name, node.id)
            prefix = '   ' + prefix

    nprefix = prefix + ('   ' if last else '\u2502  ')

    color = 'red' if not level else (
        'green' if nlevel == levels.language else (
            'blue' if nlevel == levels.dialect else None))

    util.sprint(
        '{0}{1}{2} [{3}]',
        prefix,
        s if level else (s if n.ancestors else ''),
        colored(n.name, color) if color else n.name,
        colored(n.id, color) if color else n.id)
    for i, c in enumerate(sorted(n.children, key=lambda nn: nn.name)):
        _ascii_node(c, level + 1, i == len(n.children) - 1, maxlevel, nprefix, levels)
