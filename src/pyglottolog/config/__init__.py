import types
import pathlib
import functools
import collections
import dataclasses

from clldutils.misc import nfilter
from clldutils.inifile import INI
from clldutils.jsonlib import load

__all__ = [
    'AES', 'AESSource', 'Macroarea', 'DocumentType', 'LanguageType', 'LanguoidLevel',
    'Config']


@dataclasses.dataclass
class ConfigObject:
    """
    Factory to turn INI file sections into instances of dataclasses.
    """
    @classmethod
    def from_section(cls, cfg, section, fname):
        fields = set(f.name for f in dataclasses.fields(cls))

        kw = {'name' if 'id' in cfg[section] else 'id': section}
        kw.update(cfg[section].items())
        res = cls(**{k: v for k, v in kw.items() if fields is None or k in fields})
        res._fname = fname
        return res


@dataclasses.dataclass
class Editors(ConfigObject):
    id: str
    current: bool = True
    affiliation: str = ''
    orcid: str = ''
    name: str = ''
    ord: int = 9
    github: str = None

    def __post_init__(self):
        self.current = eval(self.current)


@functools.total_ordering
@dataclasses.dataclass
class AES(ConfigObject):
    """
    AES status values

    .. seealso:: `<https://glottolog.org/langdoc/status>`_
    """
    # The attribute which is used for ordering objects of this type must come first:
    #: Sequential numeric value
    ordinal: int
    #: unique identifier (suitable as Python name, \
    #: see `<https://docs.python.org/3/reference/lexical_analysis.html#identifiers>`_)
    id: str
    #: unique human-readable name
    name: str
    #: corresponding status in the EGIDS scala
    egids: str
    #: corresponding status in the UNESCO scala
    unesco: str
    #: corresponding status in ElCat
    elcat: str
    #: Glottolog reference ID linking to further information
    reference_id: str
    icon: str = None

    def __post_init__(self):
        self.ordinal = int(self.ordinal)

    def __lt__(self, other):
        return self.ordinal < other.ordinal

    def __eq__(self, other):
        return self.ordinal == other.ordinal


@dataclasses.dataclass
class AESSource(ConfigObject):
    """
    Reference information for AES sources
    """
    id: str
    name: str
    url: str
    #: Glottolog reference ID linking to further information
    reference_id: str
    pages: str = None


@dataclasses.dataclass
class Macroarea(ConfigObject):
    """
    Glottolog macroareas (see `<https://glottolog.org/meta/glossary#macroarea>`_)
    """
    id: str
    name: str
    description: str
    #: Glottolog reference ID linking to further information
    reference_id: str

    @property
    def geojson(self):
        fname = self._fname.parent / 'macroareas' / 'voronoi' / '{}.geojson'.format(
            self.name.lower().replace(' ', '_'))
        return load(fname) if fname.exists() else None


@functools.total_ordering
@dataclasses.dataclass
class DocumentType(ConfigObject):
    """
    Document types categorize Glottolog references
    """
    rank: int
    id: str
    name: str
    description: str
    abbv: str
    bibabbv: str
    webabbr: str
    triggers: list[str]

    def __post_init__(self):
        self.rank = int(self.rank)
        self.triggers = nfilter(self.triggers.split('\n'))

    def __lt__(self, other):
        return self.rank < other.rank

    def __eq__(self, other):
        return self.rank == other.rank


@dataclasses.dataclass
class MEDType(ConfigObject):
    """
    MED (aka Descriptive Status) types (more coarse-grained document types)

    .. seealso:: `<https://glottolog.org/langdoc/status>`_
    """
    rank: str
    id: str
    name: str
    description: str
    icon: str = None

    def __post_init__(self):
        self.rank = int(self.rank)


@dataclasses.dataclass
class LanguageType(ConfigObject):
    """
    Language types categorize languages.
    """
    id: str
    #: Glottocode of the pseudo-family that languages of this type are grouped in.
    pseudo_family_id: str
    category: str  #: category name for languages of this type
    description: str


@functools.total_ordering
@dataclasses.dataclass
class LanguoidLevel(ConfigObject):
    """
    Languoid levels describe the position of languoid nodes in the classification.

    :ivar name: alias for `id`
    """
    ordinal: int
    id: str
    description: str

    def __hash__(self):
        return hash(self.id)

    def __post_init__(self):
        self.ordinal = int(self.ordinal)

    def __lt__(self, other):
        return self.ordinal < other.ordinal

    def __eq__(self, other):
        return self.ordinal == other.ordinal

    @property
    def name(self):
        return self.id


def get_ini(fname, **kw):
    fname = pathlib.Path(fname)
    if not fname.exists():
        # For old-style (<=3.4) repository layout we ship the config data with pyglottolog:
        name = fname.name if fname.name != 'hhtype.ini' else 'document_types.ini'
        fname = pathlib.Path(__file__).parent / name
    assert fname.exists()
    return INI.from_file(fname, **kw)


class Config(collections.OrderedDict):
    """
    More convenient access to objects stored as sections in INI files

    This class makes objects (i.e. INI sections) accessible as values of a `dict`, keyed by an
    `id` attribute, which is infered from the `id` or `name` option of the section and, additonally,
    under as attribute named after `id`.
    """
    __defaults__ = {}

    @classmethod
    def from_ini(cls, fname, object_class):
        ini = get_ini(fname)
        d = collections.OrderedDict()
        for sec in ini.sections():
            if object_class is types.SimpleNamespace:
                kw = {'name' if 'id' in ini[sec] else 'id': sec, '_fname': fname}
                kw.update({
                    k: eval(v) if v in ('True', 'False') else v for k, v in ini[sec].items()})
                obj = cls(**kw)
            else:
                obj = object_class.from_section(ini, sec, fname)
            d[obj.id] = obj
        res = cls(**d)
        res.__defaults__ = ini['DEFAULT']
        return res

    def __getattribute__(self, item):
        if item in self:
            return self[item]
        return dict.__getattribute__(self, item)

    def get(self, item, default=None):
        if isinstance(item, str) and item in self:
            return self[item]
        if isinstance(item, ConfigObject) and getattr(item, 'id', None) in self:
            return self[item.id]
        for li in self.values():
            if any(getattr(li, attr, None) == item for attr in ['name', 'value', 'description']):
                return li
        if default:
            return default
        raise ValueError(item)
