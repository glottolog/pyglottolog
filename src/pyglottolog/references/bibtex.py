# bibtex.py - bibtex file parsing/serialization

# TODO: make check fail on non-whitespace between entries (bibtex 'comments')

import typing
import pathlib
import functools
import collections
import unicodedata

from simplepybtex.database.input.bibtex import LowLevelParser, Parser, UndefinedMacro
from simplepybtex.scanner import PybtexSyntaxError
from simplepybtex.exceptions import PybtexError
from simplepybtex.textutils import whitespace_re
from simplepybtex.bibtex.utils import split_name_list
from simplepybtex.database import Person

from clldutils.path import memorymapped

FIELDORDER = ['author', 'editor', 'title', 'booktitle', 'journal',
              'school', 'publisher', 'address',
              'series', 'volume', 'number', 'pages', 'year', 'issn', 'url']


def load(filename, preserve_order=False, encoding=None):
    cls = collections.OrderedDict if preserve_order else dict
    return cls(iterentries(filename, encoding))


def identity(x):  # pragma: no cover
    return x


def iterentries_from_text(text, encoding='utf-8'):
    if hasattr(text, 'read'):
        text = text.read(-1)
    if not isinstance(text, str):
        text = text.decode(encoding)
    for entrytype, (bibkey, fields) in LowLevelParser(text):
        fields = {
            name.lower(): whitespace_re.sub(' ', ''.join(values)).strip()
            for name, values in fields}
        yield bibkey, (entrytype, fields)


def iterentries(filename: typing.Union[str, pathlib.Path], encoding=None)\
        -> typing.Generator[typing.Tuple[str, typing.Tuple[str, dict]], None, None]:
    encoding = encoding or 'utf8'
    with memorymapped(str(filename)) as source:
        try:
            for bibkey, (entrytype, fields) in iterentries_from_text(source, encoding):
                yield bibkey, (entrytype, fields)
        except PybtexSyntaxError as e:  # pragma: no cover
            debug_pybtex(source, e)


def debug_pybtex(source, e):  # pragma: no cover
    start, line, pos = e.error_context_info
    print('BIBTEX ERROR on line %d, last parsed lines:' % line)
    print(source[start:start + 500].decode('utf8') + '...')
    raise e


def names(s):
    for name in split_name_list(s):
        try:
            yield Name.from_string(name)
        except PybtexError as e:  # pragma: no cover
            print(repr(e))


class Name(collections.namedtuple('Name', 'prelast last given lineage')):

    __slots__ = ()

    @classmethod
    def from_string(cls, name):
        person = Person(name)
        ntypes = ('prelast_names', 'last_names', 'first_names', 'middle_names', 'lineage_names')
        prelast, last, first, middle, lineage = (' '.join(getattr(person, part)) for part in ntypes)
        given = ' '.join(n for n in (first, middle) if n)
        return cls(prelast, last, given, lineage)


def save(entries, filename, sortkey, encoding='utf-8', normalize='NFC'):
    with open(str(filename), 'w', encoding=encoding, errors='strict') as fd:
        dump(entries, fd, sortkey, normalize)


def dump(entries, fd, sortkey=None, normalize='NFC'):
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
    r"""Reserved characters (* -> en-/decoded by latexcodec)
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
    fd.write(u'# -*- coding: utf-8 -*-\n')
    for bibkey, (entrytype, fields) in items:
        fd.write(u'@%s{%s' % (entrytype, bibkey))
        for k, v in fieldorder.itersorted(fields):
            fd.write(u',\n    %s = {%s}' % (k, normalize(v.strip())))
        fd.write(u'\n}\n' if fields else u',\n}\n')


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


def check(filename, encoding=None):
    parser = CheckParser(encoding=encoding)
    parser.parse_file(str(filename))
    return parser.error_count


class CheckParser(Parser):
    """Unline LowLevelParser also parses names, macros, etc."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_count = 0

    def handle_error(self, error):  # pragma: no cover
        print('%r' % error)
        self.error_count += 1
        if not isinstance(error, UndefinedMacro):
            raise error

    def process_entry(self, *args, **kwargs):
        try:
            super().process_entry(*args, **kwargs)
        except PybtexError as e:  # pragma: no cover
            print(e)
            self.error_count += 1
