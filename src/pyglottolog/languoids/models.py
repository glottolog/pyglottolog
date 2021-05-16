import re
import typing
import collections

import attr
import markdown
import pycountry
from clldutils.misc import slug, nfilter
from clldutils import jsonlib
from dateutil import parser
import purl

from ..util import message
from ..config import AESSource, AES
from ..references import Entry

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


@attr.s(hash=True)
class Link(object):
    url = attr.ib()  #:
    label = attr.ib(default=None)  #:

    @property
    def domain(self):
        return purl.URL(self.url).domain()

    @classmethod
    def from_string(cls, s):
        s = s.strip()
        if s.startswith('['):
            assert s.endswith(')') and '](' in s
            return cls(*reversed(s[1:-1].split('](')))
        return cls(s)

    @classmethod
    def from_(cls, obj):
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, str):
            return cls.from_string(obj)
        if isinstance(obj, (list, tuple)) and len(obj) == 2:
            return cls(*obj)
        if isinstance(obj, dict):
            return cls(**obj)
        raise TypeError()

    def to_string(self):
        if self.label:
            return '[{0}]({1})'.format(self.label, self.url)
        return self.url

    def __json__(self):
        return attr.asdict(self)


class Glottocodes(object):
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
                yield '{0}{1}'.format(alpha, n)

    def new(self, name, dry_run=False):
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
        return Glottocode('%s%s' % (alpha, num))


class Glottocode(str):
    regex = r'[a-z0-9]{4}[0-9]{4}'
    pattern = re.compile(regex + r'$')

    def __new__(cls, content):
        if not cls.pattern.match(content):
            raise ValueError(content)
        return str.__new__(cls, content)

    def split(self):
        return self[:4], int(self[4:])


@attr.s
class Reference(object):
    """
    A reference of a bibliographical record in Glottolog.
    """
    key = attr.ib()  #:
    pages = attr.ib(default=None)  #:
    trigger = attr.ib(default=None)
    pattern = re.compile(
        r"\*\*(?P<key>[a-z0-9\-_]+:[a-zA-Z.?\-;*'/()\[\]!_:0-9\u2014]+?)\*\*"
        r"(:(?P<pages>[0-9\-f]+))?"
        r'(<trigger "(?P<trigger>[^\"]+)">)?')
    old_pattern = re.compile(r'[^\[]+\[(?P<pages>[^\]]*)\]\s*\([0-9]+\s+(?P<key>[^\)]+)\)')

    def __str__(self):
        res = '**{0.key}**'.format(self)
        if self.pages:
            res += ':{0.pages}'.format(self)
        if self.trigger:
            res += '<trigger "{0.trigger}">'.format(self)
        return res

    def get_source(self, api) -> Entry:
        """
        Retrieve the referenced bibliographical record.
        """
        return api.bibfiles[self.bibname][self.bibkey]

    @property
    def provider(self):
        return self.key.split(':')[0]

    @property
    def bibname(self):
        return '{0}.bib'.format(self.provider)

    @property
    def bibkey(self):
        return self.key.split(':', 1)[1]

    @classmethod
    def from_match(cls, match):
        assert match
        return cls(**match.groupdict())

    @classmethod
    def from_string(cls, string, pattern=None):
        try:
            return cls.from_match((pattern or cls.pattern).match(string.strip()))
        except AssertionError:
            raise ValueError('Invalid reference: {0}'.format(string))

    @classmethod
    def from_list(cls, list_, pattern=None):
        res = []
        for s in list_:
            if s.strip():
                try:
                    res.append(cls.from_string(s, pattern=pattern))
                except AssertionError:  # pragma: no cover
                    raise ValueError('invalid ref: {0}'.format(s))
        return res


@attr.s
class Country(object):
    """
    Glottolog languoids can be related to the countries they are spoken in. These
    countries are identified by ISO 3166 Alpha-2 codes.

    .. see also:: https://en.wikipedia.org/wiki/ISO_3166-1
    """
    id = attr.ib()  #: ISO 3166 alpha 2 code
    name = attr.ib()  #: name

    def __str__(self):
        return self._format()

    def _format(self, minimal=True):
        tmpl = '{0.name} ({0.id})' if not minimal else '{0.id}'
        return tmpl.format(self)

    @classmethod
    def from_name(cls, name):
        res = pycountry.countries.get(name=name)
        if res:
            return cls(id=res.alpha_2, name=res.name)

    @classmethod
    def from_id(cls, id_):
        res = pycountry.countries.get(alpha_2=id_)
        if res:
            return cls(id=res.alpha_2, name=res.name)

    @classmethod
    def from_text(cls, text):
        match = re.search(r'(?P<code_only>^[A-Z]{2}$)|\(?(?P<code>[A-Z]{2})\)?', text)
        if match:
            code = match.group('code_only') or match.group('code')
            return cls.from_id(code)
        return cls.from_name(text)


@attr.s
class ClassificationComment(object):
    """
    Commentary on the classification of the languoid
    """
    #: Commentary on the internal classification of the descendants of the languoid
    sub = attr.ib(default=None)
    #: References for the internal classification
    subrefs: typing.List[Reference] = attr.ib(
        default=attr.Factory(list), converter=Reference.from_list)
    #: Commentary on the classification of the languoid within its family
    family = attr.ib(default=None)
    #: References for the family classification
    familyrefs: typing.List[Reference] = attr.ib(
        default=attr.Factory(list), converter=Reference.from_list)

    def merged_refs(self, type):
        assert type in ['sub', 'family']
        res = collections.defaultdict(set)
        for m in Reference.pattern.finditer(getattr(self, type) or ''):
            res[m.group('key')].add(m.group('pages'))
        for ref in getattr(self, type + 'refs'):
            res[ref.key].add(ref.pages)
        return [
            Reference(key=key, pages=';'.join(sorted(nfilter(pages))) or None)
            for key, pages in res.items()]

    def check(self, lang, keys, log):
        for attrib in ['subrefs', 'familyrefs']:
            for ref in getattr(self, attrib):
                if ref.key not in keys:
                    log.error(message(
                        lang, 'classification {0}: invalid bibkey: {1}'.format(attrib, ref.key)))

        for attrib in ['sub', 'family']:
            comment = getattr(self, attrib)
            if comment:
                for m in Reference.pattern.finditer(comment):
                    if m.group('key') not in keys:
                        log.error(message(
                            lang,
                            'classification {0}: invalid bibkey: {1}'.format(
                                attrib, m.group('key'))))
        return False


@attr.s
class ISORetirement(object):
    """
    Information extracted from accepted ISO 639-3 change requests about retired ISO codes
    associated with the languoid.
    """
    code = attr.ib(default=None)  #: Retired ISO 639-3 code
    name = attr.ib(default=None)  #: Name of the retired ISO language
    change_request = attr.ib(default=None)  #: Number of the ISO change request
    effective = attr.ib(default=None)  #: Date of acceptance of the change request
    reason = attr.ib(default=None)  #: Reason to retire the ISO code
    change_to = attr.ib(default=attr.Factory(list))  #: List of ISO codes replacing the retired code
    remedy = attr.ib(default=None)  #: What to do about the retired code
    comment = attr.ib(converter=lambda s: s.replace('\n.', '\n') if s else s, default=None)  #:

    def asdict(self):
        return attr.asdict(self)

    __json__ = asdict


@attr.s
class Endangerment(object):
    """
    Info about the endangerment status of the languoid
    """
    status: AES = attr.ib(validator=attr.validators.instance_of(AES))  #:
    source: AESSource = attr.ib(validator=attr.validators.instance_of(AESSource))  #:
    comment = attr.ib()  #:
    #: Date when the endangerment status was assessed
    date = attr.ib(converter=parser.parse)

    def __json__(self):
        res = attr.asdict(self, recurse=True)
        res['date'] = res['date'].isoformat().split('T')[0]
        return res


def valid_ethnologue_versions(inst, attr, value):
    pattern = re.compile(r'(E[1-9][0-9]|ISO 639-3)$')
    if not all(bool(pattern.match(x)) for x in value):  # pragma: no cover
        raise ValueError('invalid ethnologue_versions: {0}'.format('/'.join(value)))


def valid_comment_type(inst, attr, value):
    if value not in ['spurious', 'missing']:
        raise ValueError('invalid comment type: {0}'.format(value))


def valid_comment(inst, attr, value):
    if not value or not isinstance(value, str):
        raise ValueError(value)


@attr.s
class EthnologueComment(object):
    """
    Commentary about the classification of the languoid according to Ethnologue
    """
    # There's the isohid field which says which iso/hid the comment concerns.
    isohid = attr.ib()

    #: Either
    #:
    #: - "spurious" meaning the comment is to explain why the languoid in question is \
    #:   spurious and in which Ethnologue (as below) that is/was
    #: - "missing" meaning the comment is to explain why the languoid in question is \
    #:   missing (as a language entry) and in which Ethnologue (as below) that is/was
    comment_type = attr.ib(validator=valid_comment_type, converter=lambda s: s.lower())

    #: Which Ethnologue version(s)
    #: from E16-E19 the comment pertains to, joined by /:s. E.g. E16/E17. In the case of
    #: comment_type=spurious, E16/E17 in the version field means that the code was spurious
    #: in E16/E17 but no longer spurious in E18/E19. In the case of comment_type=missing,
    #: E16/E17 would mean that the code was missing from E16/E17, but present in E18/E19.
    #: If the comment concerns a language where versions would be the empty string,
    #: instead the string ISO 639-3 appears.
    ethnologue_versions = attr.ib(
        default='',
        validator=valid_ethnologue_versions,
        converter=lambda s: s.replace('693', '639').split('/'))
    comment = attr.ib(default=None, validator=valid_comment)  #:

    def __json__(self):
        return attr.asdict(self)

    def check(self, lang, keys, log):
        try:
            markdown.markdown(self.comment)
        except Exception as e:  # pragma: no cover
            log.error(message(lang, 'ethnologue comment: invalid markup: {0}'.format(e)))
        for m in Reference.pattern.finditer(self.comment):
            if m.group('key') not in keys:
                log.error(message(lang, 'ethnologue comment: invalid bibkey: {0}'.format(
                    m.group('key'))))
        return False
