# bibtex.py - bibtex file parsing/serialization
"""
BibTeX parsing functionality.
"""
# TODO:  # pylint: disable=fixme
# make check fail on non-whitespace between entries (bibtex 'comments')

import functools
import collections
import unicodedata
from typing import Union, Optional, Literal, Protocol
from collections.abc import Iterable, Generator

from simplepybtex.database.input.bibtex import LowLevelParser, Parser, UndefinedMacro
from simplepybtex.scanner import PybtexSyntaxError
from simplepybtex.exceptions import PybtexError
from simplepybtex.textutils import whitespace_re

from clldutils.path import memorymapped

from pyglottolog.util import PathType

BibtexTypeAndFields = tuple[str, dict[str, str]]
EntryType = tuple[str, BibtexTypeAndFields]
EntryDictType = dict[str, BibtexTypeAndFields]
FIELDORDER = ['author', 'editor', 'title', 'booktitle', 'journal',
              'school', 'publisher', 'address',
              'series', 'volume', 'number', 'pages', 'year', 'issn', 'url']


def load(
        filename: PathType,
        preserve_order: bool = False,
        encoding: Optional[str] = None,
) -> EntryDictType:
    """Read entries from a file into a dict."""
    cls = collections.OrderedDict if preserve_order else dict
    return cls(iterentries(filename, encoding))


def identity(x):  # pragma: no cover  # pylint: disable=C0116
    return x


def iterentries_from_text(text, encoding='utf-8') -> Generator[EntryType, None, None]:
    """Read entries from text or file-like objects."""
    if hasattr(text, 'read'):
        text = text.read(-1)
    if not isinstance(text, str):
        text = text.decode(encoding)
    for entrytype, (bibkey, fields) in LowLevelParser(text):
        fields = {
            name.lower(): whitespace_re.sub(' ', ''.join(values)).strip()
            for name, values in fields}
        yield bibkey, (entrytype, fields)


def iterentries(
        filename: PathType,
        encoding: Optional[str] = None,
) -> Generator[EntryType, None, None]:
    """Read entries from a file."""
    encoding = encoding or 'utf8'
    with memorymapped(str(filename)) as source:
        try:
            yield from iterentries_from_text(source, encoding)
        except PybtexSyntaxError as e:  # pragma: no cover
            debug_pybtex(source, e)


def debug_pybtex(source, e):  # pragma: no cover  # pylint: disable=C0116
    start, line, _ = e.error_context_info
    print(f'BIBTEX ERROR on line {line}, last parsed lines:')
    print(source[start:start + 500].decode('utf8') + '...')
    raise e


def save(
        entries: Union[dict[str, BibtexTypeAndFields], Iterable[EntryType]],
        filename: PathType,
        sortkey: Optional[Literal['bibkey']],
        encoding='utf-8',
        normalize: Optional[Literal['', 'NFC', 'NFKC', 'NFD', 'NFKD']] = 'NFC',
):
    """Write entries as BibTeX to disk."""
    with open(str(filename), 'w', encoding=encoding, errors='strict') as fd:
        dump(entries, fd, sortkey, normalize)


class SupportsWrite(Protocol):  # pylint: disable=C0115,R0903
    def write(self, s: str):  # pylint: disable=C0116
        ...


def dump(
        entries: Union[dict[str, BibtexTypeAndFields], Iterable[EntryType]],
        fd: SupportsWrite,
        sortkey: Optional[Literal['bibkey']] = None,
        normalize: Optional[Literal['', 'NFC', 'NFKC', 'NFD', 'NFKD']] = 'NFC',
):
    """Write entries in BibTeX format to fd."""
    assert sortkey in [None, 'bibkey']
    if sortkey is None:
        if isinstance(entries, collections.OrderedDict):  # pragma: no cover
            items = entries.items()
        elif isinstance(entries, dict):  # pragma: no cover
            raise ValueError('dump needs sortkey or ordered entries')
        else:
            items = entries
    else:  # elif sortkey == 'bibkey':
        items = (
            (bibkey, entries[bibkey])
            for bibkey in sorted(entries, key=lambda bibkey: bibkey.lower()))
    _ = r"""Reserved characters (* -> en-/decoded by latexcodec)
    * #: \#
      $: \$
      %: \%
      ^: \^{} \textasciicircum
    * &: \&
    * _: \_
      {: \{
      }: \}
      ~: \~{} \textasciitilde
      \: \textbackslash{}
      <: \textless
      >: \textgreater
    """
    assert normalize in (None, '', 'NFC', 'NFKC', 'NFD', 'NFKD')
    if normalize:
        normalize = functools.partial(unicodedata.normalize, normalize)
    else:  # pragma: no cover
        normalize = identity
    fd.write('# -*- coding: utf-8 -*-\n')
    for bibkey, (entrytype, fields) in items:
        fd.write(f'@{entrytype}{{{bibkey}')
        for k, v in fieldorder.itersorted(fields):
            fd.write(f',\n    {k} = {{{normalize(v.strip())}}}')
        fd.write('\n}\n' if fields else ',\n}\n')


class Ordering(dict):
    """Key order for iterating over dicts (unknown keys last alphabetic)."""

    _missing = float('inf')

    @classmethod
    def fromlist(cls, keys):
        """Define the order of keys as given."""
        return cls((k, i) for i, k in enumerate(keys))

    def itersorted(self, dct):
        """Iterate over dct (key, value) pairs in the defined order."""
        for key in sorted(dct, key=self._itersorted_key):
            yield key, dct[key]

    def _itersorted_key(self, key):
        return self[key], key

    def __missing__(self, key):
        return self._missing


fieldorder = Ordering.fromlist(FIELDORDER)


def check(filename: PathType, encoding: Optional[str] = None) -> int:
    """Parse a bibtex file and report error count."""
    parser = CheckParser(encoding=encoding)
    parser.parse_file(str(filename))
    return parser.error_count


class CheckParser(Parser):
    """Unline LowLevelParser also parses names, macros, etc."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_count = 0

    def handle_error(self, error):  # pragma: no cover
        print(f'{error!r}')
        self.error_count += 1
        if not isinstance(error, UndefinedMacro):
            raise error

    def process_entry(self, *args, **kwargs):
        try:
            super().process_entry(*args, **kwargs)
        except PybtexError as e:  # pragma: no cover
            print(e)
            self.error_count += 1
