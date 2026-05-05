# hhtypes.py
"""
Handling content of hhtype fields.
"""
import re
import functools
import itertools

from ..util import Trigger
from ..config import get_ini

__all__ = ['HHType', 'HHTypes']


@functools.total_ordering
class HHType:
    """HH type, aka document type."""
    def __init__(self, s, p):
        self.name: str = s
        self.id: str = p.get(s, 'id')
        self.rank: int = p.getint(s, 'rank')
        self.abbv: str = p.get(s, 'abbv')
        self.bibabbv: str = p.get(s, 'bibabbv')
        self.description: str = p.get(s, 'description')
        self.triggers: list[Trigger] = [
            Trigger('hhtype', self.id, t)
            for t in p.get(s, 'triggers').strip().splitlines() or []]

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.id} rank={self.rank}>'

    def __eq__(self, other):
        return self.rank == other.rank

    def __lt__(self, other):
        return self.rank < other.rank


class HHTypes:
    """List-like container of HH types, aka document types."""
    _rekillparen = re.compile(r" \([^)]*\)")

    _respcomsemic = re.compile(r"[;,]\s?")

    def __init__(self, fpath):
        ini = get_ini(fpath, interpolation=None)
        self._types = sorted([HHType(s, ini) for s in ini.sections()], reverse=True)
        self._type_by_id = {t.id: t for t in self._types}

    @classmethod
    def parse(cls, s: str) -> list[str]:  # pylint: disable=C0116
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
    def triggers(self) -> list[Trigger]:  # pylint: disable=C0116
        return list(itertools.chain.from_iterable(t.triggers for t in self))
