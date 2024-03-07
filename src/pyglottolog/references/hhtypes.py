# hhtypes.py

import re
import functools
import itertools

from ..util import Trigger
from ..config import get_ini

__all__ = ['HHType', 'HHTypes']


@functools.total_ordering
class HHType(object):

    def __init__(self, s, p):
        self.name = s
        self.id = p.get(s, 'id')
        self.rank = p.getint(s, 'rank')
        self.abbv = p.get(s, 'abbv')
        self.bibabbv = p.get(s, 'bibabbv')
        self.description = p.get(s, 'description')
        self.triggers = [Trigger('hhtype', self.id, t)
                         for t in p.get(s, 'triggers').strip().splitlines() or []]

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.id} rank={self.rank}>'

    def __eq__(self, other):
        return self.rank == other.rank

    def __lt__(self, other):
        return self.rank < other.rank


class HHTypes(object):

    _rekillparen = re.compile(r" \([^)]*\)")

    _respcomsemic = re.compile(r"[;,]\s?")

    def __init__(self, fpath):
        ini = get_ini(fpath, interpolation=None)
        self._types = sorted([HHType(s, ini) for s in ini.sections()], reverse=True)
        self._type_by_id = {t.id: t for t in self._types}

    @classmethod
    def parse(cls, s):
        return cls._respcomsemic.split(cls._rekillparen.sub("", s))

    def __iter__(self):
        return iter(self._types)

    def __len__(self):
        return len(self._types)

    def __contains__(self, item):
        return item in self._type_by_id

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._types[item]
        return self._type_by_id.get(item, self._type_by_id.get('unknown'))

    @functools.cached_property
    def triggers(self):
        flattened = itertools.chain.from_iterable(t.triggers for t in self)
        return list(flattened)
