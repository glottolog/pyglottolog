import pathlib
import collections

import attr
from clldutils.misc import nfilter
from clldutils.inifile import INI

__all__ = [
    'AES', 'AESSource', 'Macroarea', 'DocumentType', 'LanguageType', 'LanguoidLevel',
    'Generic', 'Config']


class ConfigObject(object):
    """
    Factory to turn INI file sections into instances of `@attr.s` classes.
    """
    @classmethod
    def from_section(cls, cfg, section):
        try:
            fields = set(f.name for f in attr.fields(cls))
        except attr.exceptions.NotAnAttrsClassError:
            fields = None

        kw = {'name' if 'id' in cfg[section] else 'id': section}
        kw.update(cfg[section].items())
        return cls(**{k: v for k, v in kw.items() if fields is None or k in fields})


class Generic(ConfigObject):
    """
    Make config options available as attributes.
    """
    def __init__(self, **kw):
        for k, v in kw.items():
            if v in ['True', 'False']:
                v = eval(v)
            setattr(self, k, v)


@attr.s
class AES(ConfigObject):
    """
    AES status values

    .. seealso:: `<https://glottolog.org/langdoc/status>`_
    """
    # The attribute which is used for ordering objects of this type must come first:
    #: Sequential numeric value
    ordinal = attr.ib(converter=int)
    #: unique identifier (suitable as Python name, \
    #: see `<https://docs.python.org/3/reference/lexical_analysis.html#identifiers>`_)
    id = attr.ib()
    #: unique human-readable name
    name = attr.ib()
    #: corresponding status in the EGIDS scala
    egids = attr.ib()
    #: corresponding status in the UNESCO scala
    unesco = attr.ib()
    #: corresponding status in ElCat
    elcat = attr.ib()
    #: Glottolog reference ID linking to further information
    reference_id = attr.ib()
    icon = attr.ib(default=None)


@attr.s
class AESSource(ConfigObject):
    """
    Reference information for AES sources
    """
    id = attr.ib()  #:
    name = attr.ib()  #:
    url = attr.ib()  #:
    #: Glottolog reference ID linking to further information
    reference_id = attr.ib()
    pages = attr.ib(default=None)  #:


@attr.s
class Macroarea(ConfigObject):
    """
    Glottolog macroareas (see `<https://glottolog.org/meta/glossary#macroarea>`_)
    """
    id = attr.ib()  #:
    name = attr.ib()  #:
    description = attr.ib()  #:
    #: Glottolog reference ID linking to further information
    reference_id = attr.ib()


@attr.s
class DocumentType(ConfigObject):
    """
    Document types categorize Glottolog references
    """
    rank = attr.ib(converter=int)  #:
    id = attr.ib()  #:
    name = attr.ib()  #:
    description = attr.ib()  #:
    abbv = attr.ib()
    bibabbv = attr.ib()
    webabbr = attr.ib()
    triggers = attr.ib(converter=lambda s: nfilter(s.split('\n')))


@attr.s
class MEDType(ConfigObject):
    """
    MED (aka Descriptive Status) types (more coarse-grained document types)

    .. seealso:: `<https://glottolog.org/langdoc/status>`_
    """
    rank = attr.ib(converter=int)  #:
    id = attr.ib()  #:
    name = attr.ib()  #:
    description = attr.ib()  #:
    icon = attr.ib(default=None)


@attr.s
class LanguageType(ConfigObject):
    """
    Language types categorize languages.
    """
    id = attr.ib()  #:
    #: Glottocode of the pseudo-family that languages of this type are grouped in.
    pseudo_family_id = attr.ib()
    category = attr.ib()  #: category name for languages of this type
    description = attr.ib()  #:


@attr.s(hash=True)
class LanguoidLevel(ConfigObject):
    """
    Languoid levels describe the position of languoid nodes in the classification.

    :ivar name: alias for `id`
    """
    ordinal = attr.ib(converter=int)  #:
    id = attr.ib()  #:
    description = attr.ib()  #:

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
            obj = object_class.from_section(ini, sec)
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
