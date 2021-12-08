# bibfiles.py - ordered collection of bibfiles with load/save api

import re
import math
import typing
import pathlib
import datetime
import functools
import collections
import unicodedata

import attr

from clldutils.misc import lazyproperty
from clldutils.path import memorymapped
from clldutils.source import Source
from clldutils.text import split_text
from clldutils.inifile import INI
from clldutils.attrlib import cmp_off

from . import bibtex
from . import util
from ..config import MEDType
from .bibfiles_db import Database

__all__ = ['BibFiles', 'BibFile', 'Entry']

ATTRS_VERSION = tuple(int(v) for v in getattr(attr, '__version__', '20.1').split('.'))

BIBFILES = 'bibfiles.sqlite3'

DOCTYPES = {k: k for k in ['grammar',
                           'grammar_sketch',
                           'dictionary',
                           'specific_feature',
                           'phonology',
                           'text',
                           'new_testament',
                           'wordlist',
                           'comparative',
                           'minimal',
                           'socling',
                           'dialectology',
                           'overview',
                           'ethnographic',
                           'bibliographical',
                           'unknown']}

PREF_YEAR_PATTERN = re.compile(r'\[(?P<year>(1|2)[0-9]{3})(\-[0-9]+)?\]')

YEAR_PATTERN = re.compile(r'(?P<year>(1|2)[0-9]{3})')


class BibFiles(list):
    """Ordered collection of `BibFile` objects accessible by filname or index."""

    @classmethod
    def from_path(cls, path: typing.Union[str, pathlib.Path], api=None) -> 'BibFiles':
        """BibTeX files from `<path>/bibtex/*.bib` if listed in `<path>/BIBFILES.ini`."""
        path = pathlib.Path(path)
        ini = INI.from_file(path / 'BIBFILES.ini', interpolation=None)
        return cls(cls._iterbibfiles(ini, path / 'bibtex', api=api))

    @staticmethod
    def _iterbibfiles(ini, bibtex_path, api=None):
        for sec in ini.sections():
            if sec.endswith('.bib'):
                fpath = bibtex_path / sec
                if not fpath.exists():  # pragma: no cover
                    raise ValueError('invalid bibtex file referenced in BIBFILES.ini')
                yield BibFile(fname=fpath, api=api, **ini[sec])

    def __init__(self, bibfiles):
        super().__init__(bibfiles)
        self._map = {b.fname.name: b for b in self}

    def __getitem__(self, index_or_filename: typing.Union[int, str])\
            -> typing.Union['BibFile', 'Entry']:
        """Retrieve a bibfile by index or filename or an entry by qualified key.

        :param index_or_filename: Either an `int` index, or a bibfile name, or a \
        provider-qualified BibTeX key in the form `<prov>:<key>`.
        :return: A `BibFile` instance, or an `Entry` instance.
        """
        if isinstance(index_or_filename, str):
            if ':' in index_or_filename:
                stem, key = index_or_filename.split(':', maxsplit=1)
                return self._map['{}.bib'.format(stem)][key]
            if not index_or_filename.endswith('.bib'):
                index_or_filename += '.bib'
            return self._map[index_or_filename]
        return super().__getitem__(index_or_filename)

    def to_sqlite(self, filepath=BIBFILES, rebuild=False, verbose=False):
        """Return a database with the bibfiles loaded."""
        return Database.from_bibfiles(self, filepath, rebuild=rebuild, verbose=verbose)

    def roundtrip_all(self):
        """Load and save all bibfiles with the current settings."""
        return [b.roundtrip() for b in self]


def file_if_exists(i, a, value):
    if value.exists() and not value.is_file():
        raise ValueError('invalid path')  # pragma: no cover


@attr.s
class BibFile(object):
    """
    Represents a BibTeX file, storing a provider's bibliography, providing easy access to its
    records.
    """
    fname: pathlib.Path = attr.ib(validator=file_if_exists)
    name = attr.ib(default=None)  #: Short name of the bibliography
    title = attr.ib(default=None)  #: Title of the bibliography
    description = attr.ib(default=None)  #: The provenance of the bibliography
    abbr = attr.ib(default=None)
    encoding = attr.ib(default='utf-8')
    normalize = attr.ib(default='NFC')
    sortkey = attr.ib(
        default=None,
        converter=lambda s: None if s is None or s.lower() == 'none' else s)
    priority = attr.ib(default=0, converter=int)
    url = attr.ib(default=None)  #: URL pointing to the source of the bibliography
    curation = attr.ib(default=None)  #: Curation policy for the bibliography at Glottolog
    api = attr.ib(default=None)

    @property
    def id(self):
        return self.fname.stem

    def __getitem__(self, item: str) -> 'Entry':
        """
        :param item: BibTeX citation key of an entry
        :raises KeyError: if no matching `Entry` is contained in the `BibFile`
        """
        if item.startswith(self.id + ':'):
            item = item.split(':', 1)[1]
        text = None
        with memorymapped(self.fname) as string:
            m = re.search(
                b'@[A-Za-z]+{' + re.escape(item.encode(self.encoding)) + rb'[\s,]', string)
            if m:
                next = string.find(b'\n@', m.end())
                if next >= 0:
                    text = string[m.start():next]
                else:
                    text = string[m.start():]
        if text:
            for k, (t, f) in bibtex.iterentries_from_text(text, encoding=self.encoding):
                return Entry(k, t, f, self, self.api)
        raise KeyError(item)

    def visit(self, visitor=None):
        entries = collections.OrderedDict()
        for entry in self.iterentries():
            if visitor is None or visitor(entry) is not True:
                entries[entry.key] = (entry.type, entry.fields)
        self.save(entries)

    @property
    def size(self):
        return self.fname.stat().st_size

    @property
    def mtime(self):
        return datetime.datetime.fromtimestamp(self.fname.stat().st_mtime)

    def iterentries(self):
        for k, (t, f) in bibtex.iterentries(filename=self.fname, encoding=self.encoding):
            yield Entry(k, t, f, self, self.api)

    def keys(self):
        return ['{0}:{1}'.format(self.id, e.key) for e in self.iterentries()]

    @property
    def glottolog_ref_id_map(self):
        return {
            e.key: e.fields['glottolog_ref_id'] for e in self.iterentries()
            if 'glottolog_ref_id' in e.fields}

    def update(self, fname, log=None):
        entries, new = collections.OrderedDict(), 0
        ref_id_map = self.glottolog_ref_id_map
        for key, (type_, fields) in bibtex.iterentries(fname, self.encoding):
            if key in ref_id_map and 'glottolog_ref_id' not in fields:
                fields['glottolog_ref_id'] = ref_id_map[key]
            else:
                new += 1
            entries[key] = (type_, fields)
        self.save(entries)
        if log:  # pragma: no cover
            log.info('{0} new entries'.format(new))

    def load(self, preserve_order=None):
        """Return entries as bibkey -> (entrytype, fields) dict."""
        if preserve_order is None:
            preserve_order = self.sortkey is None
        return bibtex.load(self.fname, preserve_order, encoding=self.encoding)

    def save(self, entries):
        """Write bibkey -> (entrytype, fields) map to file."""
        bibtex.save(
            entries,
            filename=self.fname,
            sortkey=self.sortkey,
            encoding=self.encoding,
            normalize=self.normalize)

    def __str__(self):
        return f'<{self.__class__.__name__} {self.fname.name}>'

    def check(self, log):
        entries = self.load()  # bare BibTeX syntax
        invalid = bibtex.check(filename=self.fname)  # names/macros etc.
        verdict = ('(%d invalid)' % invalid) if invalid else 'OK'
        method = log.warn if invalid else log.info
        method('%s %d %s' % (self, len(entries), verdict))
        return len(entries), verdict

    def roundtrip(self):
        print(self)
        self.save(self.load())

    def show_characters(self, include_plain=False):
        """Display character-frequencies (excluding printable ASCII)."""
        with self.fname.open(encoding=self.encoding) as fd:
            text = fd.read()
        hist = collections.Counter(text)
        table = '\n'.join(
            '%d\t%-9r\t%s\t%s' % (n, c, c, unicodedata.name(c, ''))
            for c, n in hist.most_common()
            if include_plain or not 20 <= ord(c) <= 126)
        print(table)


@functools.total_ordering
@attr.s(**cmp_off)
class Entry(object):
    """
    Represents an entry in a `BibFile`, i.e. a bibliographical record.

    .. note::

        `Entry` instances are orderable. The ordering is the one used to compute MEDs, i.e.

        - grammars are "better" than other document types,
        - more pages is "better" than less,
        - more recent is "better" than old.

    .. code-block:: python

        >>> g = pyglottolog.Glottolog()
        >>> g.bibfiles['hh:g:MacDonell:Sanskrit'] > g.bibfiles['hh:hv:Weijnen:Nederlandse']
        True
        >>> refs = g.refs_by_languoid(gl.bibfiles['hh'])
        >>> sorted(refs[0]['stan1295'])[-1].med_type.name
        'long grammar'
    """
    key = attr.ib()  #:
    type = attr.ib()  #: BibTeX entry type
    fields: dict = attr.ib()  #: The metadata of the record
    bib = attr.ib()
    api = attr.ib(default=None)

    # FIXME: add method to apply triggers!

    lgcode_regex = r'[a-z0-9]{4}[0-9]{4}|[a-z]{3}|NOCODE_[A-Z][^\s\]]+'
    lgcode_in_brackets_pattern = re.compile(r"\[(" + lgcode_regex + r")]")
    recomma = re.compile(r"[,/]\s?")
    lgcode_pattern = re.compile(lgcode_regex + "$")

    def __eq__(self, other):
        return self.weight == other.weight

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return self.weight < other.weight

    @property
    def _defined_doctypes(self):
        return collections.OrderedDict((hht.id, hht.id) for hht in self.api.hhtypes) \
            if self.api else DOCTYPES

    @lazyproperty
    def weight(self):
        doctypes = self._defined_doctypes
        index = len(doctypes)
        doctype = None

        for _doctype in self.doctypes(doctypes)[0]:
            index = list(doctypes.values()).index(_doctype)
            doctype = getattr(_doctype, 'id', _doctype)
            break

        # the number of pages is divided by number of doctypes times number of described languages
        pages = int(math.ceil(
            float(self.pages_int or 0) /  # noqa: W504
            ((len(self.doctypes(doctypes)[0]) or 1) *  # noqa: W504
             (len(self.lgcodes(self.fields.get('lgcode', ''))) or 1))))

        if doctype == 'grammar' and pages >= 300:
            index = -1

        return -index, pages, self.year_int or 0, self.id

    @lazyproperty
    def med_type(self) -> MEDType:
        """
        The entry's type on the MED scale.
        """
        if self.api:
            doctypes = list(self._defined_doctypes.keys())
            index = -self.weight[0]
            if index == -1:
                return self.api.med_types.long_grammar
            if 'dictionary' in doctypes and index < doctypes.index('dictionary'):
                return self.api.med_types.get(doctypes[index])
            if 'wordlist' in doctypes and index < doctypes.index('wordlist'):
                return self.api.med_types.phonology_or_text
            return self.api.med_types.wordlist_or_less

    @lazyproperty
    def year_int(self):
        if self.fields.get('year'):
            # prefer years in brackets over the first 4-digit number.
            match = PREF_YEAR_PATTERN.search(self.fields.get('year'))
            if match:
                return int(match.group('year'))
            match = YEAR_PATTERN.search(self.fields.get('year'))
            if match:
                return int(match.group('year'))

    @lazyproperty
    def pages_int(self):
        if self.fields.get('numberofpages'):
            try:
                pages = int(self.fields.get('numberofpages').strip())
                if pages < util.MAX_PAGE:
                    return pages
            except ValueError:
                pass

        if self.fields.get('pages'):
            return util.compute_pages(self.fields['pages'])[2]

    @lazyproperty
    def publisher_and_address(self):
        p = self.fields.get('publisher')
        if p and ':' in p:
            address, publisher = [s.strip() for s in p.split(':', 1)]
            if (not self.fields.get('address')) or self.fields['address'] == address:
                return publisher, address
        return p, self.fields.get('address')

    def __str__(self):
        """Return the BibTeX representation of the entry."""
        res = "@%s{%s" % (self.type, self.key)
        for k, v in bibtex.fieldorder.itersorted(self.fields):
            res += ',\n    %s = {%s}' % (k, v.strip() if hasattr(v, 'strip') else v)
        res += '\n}\n' if self.fields else ',\n}\n'
        return res

    def text(self) -> str:
        """Return the text linearization of the entry."""
        return Source(self.type, self.key, _check_id=False, **self.fields).text()

    @property
    def id(self) -> str:
        """
        The qualified entry ID, including the provider prefix.
        """
        return '{0}:{1}'.format(self.bib.id, self.key)

    @classmethod
    def lgcodes(cls, string):
        if string is None:
            return []
        codes = cls.lgcode_in_brackets_pattern.findall(string)
        if not codes:
            # ... or as comma separated list of identifiers.
            parts = [p.strip() for p in cls.recomma.split(string)]
            codes = [p for p in parts if cls.lgcode_pattern.match(p)]
            if len(codes) != len(parts):
                codes = []
        return codes

    @staticmethod
    def parse_ca(s):
        if s:
            match = re.search('computerized assignment from "(?P<trigger>[^\"]+)"', s)
            if match:
                return match.group('trigger')

    def languoids(self, langs_by_codes: dict) -> typing.Tuple[list, typing.Optional[str]]:
        """
        Expand the language codes mentioned in a reference's "lgcode" field to `Languoid` objects.
        """
        res = []
        if 'lgcode' in self.fields:
            for code in self.lgcodes(self.fields['lgcode']):
                if code in langs_by_codes:
                    res.append(langs_by_codes[code])
        return res, self.parse_ca(self.fields.get('lgcode'))

    def doctypes(self, hhtypes):
        """Ordered doctypes assigned to this entry.

        :param hhtypes: `OrderedDict` mapping doctype names to doctypes
        :return: `list` of values of `hhtypes` which apply to the entry, ordered by occurrence in\
        `hhtypes`.
        """
        res = set()
        if 'hhtype' in self.fields:
            for ss in split_text(self.fields['hhtype'], separators=',;'):
                ss = ss.split('(')[0].strip()
                if ss in hhtypes:
                    res.add(ss)
        return [v for k, v in hhtypes.items() if k in res], self.parse_ca(self.fields.get('hhtype'))
