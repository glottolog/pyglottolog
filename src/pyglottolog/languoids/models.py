"""
OO wrappers for various Glottolog data objects.
"""
import datetime
import logging
import re
from typing import Optional, Literal, get_args, TYPE_CHECKING, Union
import collections
from collections.abc import Iterable
import dataclasses
import urllib.parse

import markdown
import pycountry
from clldutils.misc import slug, nfilter
from clldutils import jsonlib
from clldutils.markup import MarkdownLink
from dateutil import parser

from ..util import message
from ..config import AESSource, AES
from ..references import Entry

if TYPE_CHECKING:  # pragma: no cover
    from . import Languoid

__all__ = [
    'Glottocode', 'Glottocodes',
    'Reference',
    'Country',
    'ClassificationComment',
    'ISORetirement',
    'Endangerment',
    'EthnologueComment',
    'Link',
]


@dataclasses.dataclass(eq=True, frozen=True)
class Link:
    """Links appear in multiple places in languoid ini files."""
    url: str
    label: str = None

    @property
    def domain(self) -> str:
        """The domain part of the URL, aka netloc."""
        return urllib.parse.urlparse(self.url).netloc

    @classmethod
    def from_string(cls, s: str) -> 'Link':
        """Simplistic parsing of links from markdown formatting."""
        s = s.strip()
        if s.startswith('['):
            assert s.endswith(')') and '](' in s
            return cls(*reversed(s[1:-1].split('](')))
        return cls(s)

    @classmethod
    def from_(cls, obj: Union['Link', str, list, tuple, dict]) -> 'Link':
        """Instantiate link from various input types."""
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, str):
            return cls.from_string(obj)
        if isinstance(obj, (list, tuple)) and len(obj) == 2:
            return cls(*obj)
        if isinstance(obj, dict):
            return cls(**obj)
        raise TypeError()

    def to_string(self) -> str:
        """Link formatted as markdown."""
        if self.label:
            return f'[{self.label}]({self.url})'
        return self.url

    def __json__(self):
        return dataclasses.asdict(self)


class Glottocodes:
    """
    Registry keeping track of glottocodes that have been dealt out.
    """
    def __init__(self, fname):
        self._fname = fname
        self._store = jsonlib.load(self._fname)

    def __contains__(self, item):
        alpha, num = Glottocode(item).split()
        return alpha in self._store and num <= self._store[alpha]

    def __iter__(self):
        for alpha, num in self._store.items():
            for n in range(1234, num + 1):
                yield f'{alpha}{n}'

    def new(self, name, dry_run=False) -> 'Glottocode':
        """Mint a new Glottocode"""
        alpha = slug(str(name))[:4]
        assert alpha
        while len(alpha) < 4:
            alpha += alpha[-1]
        num = self._store.get(alpha, 1233) + 1
        if not dry_run:
            self._store[alpha] = num
            # Store the updated dictionary of glottocodes back.
            ordered = collections.OrderedDict()
            for k in sorted(self._store.keys()):
                ordered[k] = self._store[k]
            jsonlib.dump(ordered, self._fname, indent=4)
        return Glottocode(f'{alpha}{num}')


class Glottocode(str):
    """Glottocodes are special string."""
    regex = r'[a-z0-9]{4}[0-9]{4}'
    pattern = re.compile(regex + r'$')

    def __new__(cls, content):
        if not cls.pattern.match(content):
            raise ValueError(content)
        return str.__new__(cls, content)

    def split(self) -> tuple[str, int]:
        """Split the Glottocode into alpha-numeric and numeric part."""
        return self[:4], int(self[4:])


@dataclasses.dataclass
class Reference:
    """
    A reference of a bibliographical record in Glottolog.
    """
    key: str
    pages: Optional[str] = None
    trigger: Optional[str] = None
    endtag: str = '**'
    pattern: re.Pattern = re.compile(
        r"\*\*(?P<key>[a-z0-9\-_]+:[a-zA-Z.?\-;*'/()\[\]!_:0-9\u2014]+?)(?P<endtag>\*\*|\(\*\*\))"
        r"(:(?P<pages>[0-9\-f]+))?"
        r'(<trigger "(?P<trigger>[^\"]+)">)?')
    old_pattern: re.Pattern = re.compile(r'[^\[]+\[(?P<pages>[^]]*)]\s*\([0-9]+\s+(?P<key>[^)]+)\)')

    def __str__(self):
        res = f'**{self.key}**'
        if self.pages:
            res += f':{self.pages}'
        if self.trigger:
            res += f'<trigger "{self.trigger}">'
        return res

    def get_source(self, api) -> Entry:
        """
        Retrieve the referenced bibliographical record.
        """
        return api.bibfiles[self.bibname][self.bibkey]

    @property
    def provider(self) -> str:
        """The provider id."""
        return self.key.split(':')[0]

    @property
    def bibname(self) -> str:
        """The name of the bibtex file."""
        return f'{self.provider}.bib'

    @property
    def bibkey(self) -> str:
        """The local bibtex key in the bib."""
        return self.key.split(':', 1)[1]

    @classmethod
    def from_match(cls, match: re.Match) -> 'Reference':
        """Instantiate a reference from a regex match."""
        assert match
        return cls(**match.groupdict())

    @classmethod
    def from_string(cls, string: str, pattern: Optional[re.Pattern] = None) -> 'Reference':
        """Parse a reference from a string."""
        try:
            return cls.from_match((pattern or cls.pattern).match(string.strip()))
        except AssertionError as e:
            raise ValueError(f'Invalid reference: {string}') from e

    @classmethod
    def from_list(
            cls,
            list_: Iterable[Union['Reference', str]],
            pattern: Optional[re.Pattern] = None,
    ) -> list['Reference']:
        """Turn list of strings into list of Reference instances."""
        res = []
        for s in list_:
            if isinstance(s, cls):
                res.append(s)
                continue
            if s.strip():
                try:
                    res.append(cls.from_string(s, pattern=pattern))
                except AssertionError as e:  # pragma: no cover
                    raise ValueError(f'invalid ref: {s}') from e
        return res


@dataclasses.dataclass
class Country:
    """
    Glottolog languoids can be related to the countries they are spoken in. These
    countries are identified by ISO 3166 Alpha-2 codes.

    .. see also:: https://en.wikipedia.org/wiki/ISO_3166-1
    """
    id: str  #: ISO 3166 alpha 2 code
    name: str

    def __str__(self):
        return self._format()

    def _format(self, minimal=True):
        return f'{self.name} ({self.id})' if not minimal else f'{self.id}'

    @classmethod
    def from_name(cls, name) -> Optional['Country']:  # pylint: disable=C0116
        res = pycountry.countries.get(name=name)
        if res:
            return cls(id=res.alpha_2, name=res.name)
        return None  # pragma: no cover

    @classmethod
    def from_id(cls, id_) -> Optional['Country']:  # pylint: disable=C0116
        res = pycountry.countries.get(alpha_2=id_)
        if res:
            return cls(id=res.alpha_2, name=res.name)
        return None  # pragma: no cover

    @classmethod
    def from_text(cls, text: str) -> Optional['Country']:
        """Instantiate country based on alpha_2 code or name."""
        match = re.search(r'(?P<code_only>^[A-Z]{2}$)|\(?(?P<code>[A-Z]{2})\)?', text)
        if match:
            code = match.group('code_only') or match.group('code')
            return cls.from_id(code)
        return cls.from_name(text)


@dataclasses.dataclass
class ClassificationComment:
    """
    Commentary on the classification of the languoid
    """
    #: Commentary on the internal classification of the descendants of the languoid
    sub: Optional[str] = None
    #: References for the internal classification
    subrefs: list[Reference] = dataclasses.field(default_factory=list)
    #: Commentary on the classification of the languoid within its family
    family: Optional[str] = None
    #: References for the family classification
    familyrefs: list[Reference] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        for att in ('subrefs', 'familyrefs'):
            setattr(self, att, Reference.from_list(getattr(self, att)))

    def merged_refs(self, type_: Literal['sub', 'family']) -> list[Reference]:
        """
        Get unique sources referenced for the classification type, with accumulated page ranges.
        """
        assert type_ in ['sub', 'family']
        res = collections.defaultdict(set)
        for m in Reference.pattern.finditer(getattr(self, type_) or ''):
            res[m.group('key')].add(m.group('pages'))
        for ref in getattr(self, type_ + 'refs'):
            res[ref.key].add(ref.pages)
        return [
            Reference(key=key, pages=';'.join(sorted(nfilter(pages))) or None)
            for key, pages in res.items()]

    def check(self, lang: 'Languoid', keys: list[str], log: logging.Logger):
        """Check formatting and content."""
        for attrib in ['subrefs', 'familyrefs']:
            for ref in getattr(self, attrib):
                if ref.key not in keys:
                    log.error(message(
                        lang, f'classification {attrib}: invalid bibkey: {ref.key}'))

        for attrib in ['sub', 'family']:
            comment = getattr(self, attrib)
            if comment:
                for m in Reference.pattern.finditer(comment):
                    if m.group('key') not in keys:
                        log.error(message(
                            lang, f"classification {attrib}: invalid bibkey: {m.group('key')}"))


@dataclasses.dataclass
class ISORetirement:  # pylint: disable=R0902
    """
    Information extracted from accepted ISO 639-3 change requests about retired ISO codes
    associated with the languoid.
    """
    code: Optional[str] = None  #: Retired ISO 639-3 code
    name: Optional[str] = None  #: Name of the retired ISO language
    change_request: Optional[str] = None  #: Number of the ISO change request
    effective: Optional[str] = None  #: Date of acceptance of the change request
    reason: Optional[str] = None  #: Reason to retire the ISO code
    #: List of ISO codes replacing the retired code
    change_to: list[str] = dataclasses.field(default_factory=list)
    remedy: Optional[str] = None  #: What to do about the retired code
    comment: Optional[str] = None

    def __post_init__(self):
        self.comment = self.comment.replace('\n.', '\n') if self.comment else None

    def asdict(self):  # pylint: disable=C0116
        return dataclasses.asdict(self)

    __json__ = asdict


@dataclasses.dataclass
class Endangerment:
    """
    Info about the endangerment status of the languoid
    """
    status: AES
    source: AESSource
    comment: str
    #: Date when the endangerment status was assessed
    date: datetime.datetime

    def __post_init__(self):
        assert isinstance(self.status, AES)
        assert isinstance(self.source, AESSource)
        if isinstance(self.date, str):
            self.date = parser.parse(self.date)

    def __json__(self):
        res = dataclasses.asdict(self)
        res['date'] = res['date'].isoformat().split('T')[0]
        return res

    def check(self, lang: 'Languoid', keys: list[str], log: logging.Logger):
        """Check formatting of endangerment info."""
        def repl(ml):
            if ml.url not in keys:
                log.error(message(lang, f'endangerment comment: invalid bibkey: {ml.url}'))

        if self.source and self.source.reference_id:
            ref = self.source.reference_id
            if ref not in keys:  # pragma: no cover
                log.error(message(lang, f'endangerment: invalid bibkey {ref}'))
        if self.comment:
            MarkdownLink.replace(self.comment, repl)


CommentType = Literal['spurious', 'missing']


@dataclasses.dataclass
class EthnologueComment:
    """
    Commentary about the classification of the languoid according to Ethnologue
    """
    # There's the isohid field which says which iso/hid the comment concerns.
    isohid: str

    #: Either
    #:
    #: - "spurious" meaning the comment is to explain why the languoid in question is \
    #:   spurious and in which Ethnologue (as below) that is/was
    #: - "missing" meaning the comment is to explain why the languoid in question is \
    #:   missing (as a language entry) and in which Ethnologue (as below) that is/was
    comment_type: CommentType

    #: Which Ethnologue version(s)
    #: from E16-E19 the comment pertains to, joined by /:s. E.g. E16/E17. In the case of
    #: comment_type=spurious, E16/E17 in the version field means that the code was spurious
    #: in E16/E17 but no longer spurious in E18/E19. In the case of comment_type=missing,
    #: E16/E17 would mean that the code was missing from E16/E17, but present in E18/E19.
    #: If the comment concerns a language where versions would be the empty string,
    #: instead the string ISO 639-3 appears.
    ethnologue_versions: list[str] = dataclasses.field(default_factory=list)
    comment: str = None

    def __post_init__(self):
        self.comment_type = self.comment_type.lower()
        if self.comment_type not in get_args(CommentType):
            raise ValueError(self.comment_type)

        if self.ethnologue_versions and isinstance(self.ethnologue_versions, str):
            self.ethnologue_versions = self.ethnologue_versions.replace(  # pylint: disable=E1101
                '693', '639').split('/')
        pattern = re.compile(r'(E[1-9][0-9]|ISO 639-3)$')
        if not all(bool(pattern.match(x)) for x in self.ethnologue_versions):  # pragma: no cover
            raise ValueError(f'invalid ethnologue_versions: {"/".join(self.ethnologue_versions)}')

        if not self.comment or not isinstance(self.comment, str):
            raise ValueError(self.comment)

    def __json__(self):
        return dataclasses.asdict(self)

    def check(self, lang: 'Languoid', keys: list[str], log: logging.Logger):
        """Check formatting of the comment"""
        try:
            markdown.markdown(self.comment)
        except Exception as e:  # pragma: no cover  # pylint: disable=W0718
            log.error(message(lang, f'ethnologue comment: invalid markup: {e}'))
        for m in Reference.pattern.finditer(self.comment):
            if m.group('key') not in keys:
                log.error(message(lang, f"ethnologue comment: invalid bibkey: {m.group('key')}"))
