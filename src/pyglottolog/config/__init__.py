import collections

import attr
from clldutils.misc import nfilter
from clldutils.inifile import INI
from clldutils.path import Path

__all__ = [
    'AES', 'AESSource', 'Macroarea', 'DocumentType', 'LanguageType', 'LanguoidLevel',
    'Generic', 'Config']


class ConfigObject(object):
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
    def __init__(self, **kw):
        for k, v in kw.items():
            if v in ['True', 'False']:
                v = eval(v)
            setattr(self, k, v)


@attr.s
class AES(ConfigObject):
    # The attribute which is used for ordering objects of this type must come first:
    ordinal = attr.ib(converter=int)
    id = attr.ib()
    name = attr.ib()
    egids = attr.ib()
    unesco = attr.ib()
    elcat = attr.ib()
    reference_id = attr.ib()
    icon = attr.ib(default=None)


@attr.s
class AESSource(ConfigObject):
    id = attr.ib()
    name = attr.ib()
    url = attr.ib()
    reference_id = attr.ib()
    pages = attr.ib(default=None)


@attr.s
class Macroarea(ConfigObject):
    id = attr.ib()
    name = attr.ib()
    description = attr.ib()
    reference_id = attr.ib()


@attr.s
class DocumentType(ConfigObject):
    rank = attr.ib(converter=int)
    id = attr.ib()
    name = attr.ib()
    description = attr.ib()
    abbv = attr.ib()
    bibabbv = attr.ib()
    webabbr = attr.ib()
    triggers = attr.ib(converter=lambda s: nfilter(s.split('\n')))


@attr.s
class MEDType(ConfigObject):
    rank = attr.ib(converter=int)
    id = attr.ib()
    name = attr.ib()
    description = attr.ib()
    icon = attr.ib(default=None)


@attr.s
class LanguageType(ConfigObject):
    id = attr.ib()
    pseudo_family_id = attr.ib()
    category = attr.ib()
    description = attr.ib()


@attr.s(hash=True)
class LanguoidLevel(ConfigObject):
    ordinal = attr.ib(converter=int)
    id = attr.ib()
    description = attr.ib()

    @property
    def name(self):
        return self.id


def get_ini(fname, **kw):
    fname = Path(fname)
    if not fname.exists():
        # For old-style (<=3.4) repository layout we ship the config data with pyglottolog:
        name = fname.name if fname.name != 'hhtype.ini' else 'document_types.ini'
        fname = Path(__file__).parent / name
    assert fname.exists()
    return INI.from_file(fname, **kw)


class Config(collections.OrderedDict):
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
