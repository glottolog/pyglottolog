"""
Misc utils.
"""
import copy
import pathlib
import operator
import textwrap
import itertools
import functools
from typing import Any, Union, Callable, TypeVar
from collections.abc import Sequence, Iterable, Generator

from termcolor import colored
from clldutils.iso_639_3 import ISO, download_tables

T = TypeVar('T')
PathType = Union[str, pathlib.Path]


def sprint(text: Any, *args, **kw) -> None:
    """Pretty print text"""
    if not isinstance(text, str):
        text = f'{text}'
    if args:
        text = text.format(*args)
    color = kw.pop('color', None)
    attrs = kw.pop('attrs', None)
    if color or attrs:
        text = colored(text, color=color, attrs=attrs)
    print(text)


def wrap(
        text: str,
        line_as_paragraph: bool = False,
        width: int = 80,
        break_long_words: bool = False,
        break_on_hyphens: bool = False,
        **kw,
) -> str:
    """Convenience wrapper for textwrap.wrap."""
    kw.update(width=width, break_long_words=break_long_words, break_on_hyphens=break_on_hyphens)
    lines = []
    for line in text.split('\n'):
        if not line:
            lines.append('')
        else:
            lines.extend(textwrap.wrap(line, **kw))
            if line_as_paragraph:
                lines.append('')
    return '\n'.join(lines).strip()


def message(obj: Any, msg: str) -> str:  # pylint: disable=C0116
    obj = colored(f'{obj}', 'blue', attrs=['bold'])
    return f'{obj}: {msg}'


def get_iso(d: PathType) -> ISO:
    """Retrieve an initialized ISO 639-3 object."""
    zips = sorted(list(pathlib.Path(d).glob('iso-639-3_Code_Tables_*.zip')), key=lambda p: p.name)
    if zips:
        return ISO(zips[-1])

    return ISO(download_tables(d))  # pragma: no cover


TriggerClauseType = tuple[bool, str]
TriggerGroupType = tuple[list[TriggerClauseType], list['Trigger']]


@functools.total_ordering
class Trigger:
    """
    >>> t = Trigger('f', 't', 'NOT a AND b')
    >>> t([1, 2, 3], {'a': {1, 2}, 'b': {2, 3}})
    {3}
    """
    def __init__(self, field, type_, string):
        self.field = field  #: The bibtex field triggers relate to.
        self.type = type_
        self._string = string
        self.clauses: Sequence[TriggerClauseType] = tuple(sorted([
            (False, w[4:].strip()) if w.startswith('NOT ') else (True, w.strip())
            for w in string.split(' AND ')]))

    def __eq__(self, other):
        # make triggers sortable so that we can easily group them by clauses.
        return self.clauses == other.clauses and self.cls == other.cls

    def __lt__(self, other):
        # make triggers sortable so that we can easily group them by clauses.
        return (self.clauses, self.cls) < (other.clauses, other.cls)

    @property
    def cls(self) -> tuple[str, str]:  # pylint: disable=C0116
        return self.field, self.type

    def __call__(
            self,
            allkeys: Union[Sequence[T], set[T]],
            keys_by_word: dict[str, set[T]],
    ) -> set[T]:
        """
        Evaluate a trigger, passing in all keys associated with some object, and dict mapping word
        to sets of keys triggered by the word.
        """
        allkeys = set(allkeys)
        matching = copy.copy(allkeys)  # Start out with all keys considered as matching.
        for isin, word in self.clauses:
            matching_for_clause = copy.copy(keys_by_word[word])
            if not isin:
                matching_for_clause = allkeys.difference(matching_for_clause)
            matching.intersection_update(matching_for_clause)
        return matching

    @staticmethod
    def format(label, triggers: Sequence[Union['Trigger', str]]) -> str:
        """Human-readable info about the triggers."""
        trigs = [triggers] if isinstance(triggers, Trigger) else reversed(triggers)
        from_ = ';'.join(
            [' and '.join(
                [('' if c else 'not ') + w for c, w in t.clauses]) for t in trigs])
        return f'{label} (computerized assignment from "{from_}")'

    @staticmethod
    def group(triggers: Iterable['Trigger']) -> list[TriggerGroupType]:
        """Group triggers for more efficient evaluation."""
        return [(clauses, list(trigs)) for clauses, trigs
                in itertools.groupby(sorted(triggers), lambda t: t.clauses)]


def group_first(
        iterable: Iterable[Sequence[Any]],
        groupkey: Callable[[Sequence[Any]], Any] = operator.itemgetter(0),
) -> Generator[tuple[Any, list[Sequence[Any]]], None, None]:
    """
    Note: `iterable` is expected to be appropriately sorted.

    >>> list(group_first(['abcd', 'adwe', 'cdef']))
    [('a', ['abcd', 'adwe']), ('c', ['cdef'])]
    """
    for key, group in itertools.groupby(iterable, groupkey):
        yield key, list(group)


def unique(iterable: Iterable[Any]) -> Generator[Any, None, None]:
    """Yield unique items from iterable."""
    seen = set()
    for item in iterable:
        if item not in seen:
            seen.add(item)
            yield item
