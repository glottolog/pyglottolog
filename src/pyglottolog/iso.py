"""
Functionality to integrate ISO 639-3 data.
"""
import logging
import re
import hashlib
import pathlib
import datetime
import itertools
import dataclasses
from xml.etree import ElementTree
from typing import Optional, TYPE_CHECKING, Union, Literal, get_args
from collections.abc import Generator, Iterator

from clldutils import iso_639_3
from csvw import dsv

from .references.bibtex import save, EntryType
from .util import PathType
from ._compat import StrEnum

if TYPE_CHECKING:
    from pyglottolog import Glottolog
    from pyglottolog.languoids.languoid import Languoid, LanguoidMapType

ISO_CODE_PATTERN = re.compile('[a-z]{3}$')
CACHE_DIR = 'iso_639_3_cache'
# log-level, languoid, msg:
LogMessageType = tuple[str, Union['Languoid', str], str]


def read_url(
        path: str,
        cache_dir: Optional[PathType] = None,
        log: Optional[logging.Logger] = None,
) -> str:
    """
    Delegate scraping to clldutils, since nowadays this requires tweaking the user agent as well.
    """
    if cache_dir:
        cache_dir = pathlib.Path(cache_dir)
        if log:  # pragma: no cover
            log.debug('retrieving %s ...', path)
        fpath = cache_dir / hashlib.md5(path.encode('utf8')).hexdigest()
        if not fpath.exists():
            with iso_639_3._open(path) as fp:  # pylint: disable=W0212
                fpath.write_text(fp.read().decode('utf8'), encoding='utf8')
        else:  # pragma: no cover
            if log:
                log.debug('... from cache %s', fpath)
        return fpath.read_text(encoding='utf8')

    with iso_639_3._open(path) as fp:  # pylint: disable=W0212
        return fp.read().decode('utf8')


def normalize_whitespace(s: str) -> str:
    """Turn cluster of whitespace into single space."""
    return re.sub(r'\s+', ' ', s).strip()


class RetReason(StrEnum):
    """
    Reasons for retirement of an ISO code.

    See https://iso639-3.sil.org/code_tables/download_tables#Deprecated%20Code%20Mappings
    """
    C = 'change'
    D = 'duplicate'
    N = 'non-existent'
    S = 'split'
    M = 'merge'


@dataclasses.dataclass
class Retirement:
    """A row in the retirements table."""
    Id: str  # pylint: disable=invalid-name
    Ref_Name: str  # pylint: disable=invalid-name
    Ret_Reason: Optional[RetReason]  # pylint: disable=invalid-name
    Change_To: Union[str, list[str]]  # pylint: disable=invalid-name
    Ret_Remedy: str  # pylint: disable=invalid-name
    Effective: datetime.date  # pylint: disable=invalid-name
    cr: Union[str, 'ChangeRequest'] = None

    def __post_init__(self):
        def _validate_iso_code(attr, value):
            if not ISO_CODE_PATTERN.match(value):
                raise ValueError(f'invalid ISO code in {attr}: {value}')

        _validate_iso_code('Id', self.Id)

        self.Change_To = self.Change_To or None
        if self.Change_To:
            _validate_iso_code('Change_To', self.Change_To)

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> 'Retirement':
        """Instantiate Retirement from a table row."""
        d['Ret_Reason'] = getattr(RetReason, d['Ret_Reason'], None)
        d['Ret_Remedy'] = normalize_whitespace(d['Ret_Remedy'])
        d['Effective'] = datetime.date(*[int(p) for p in d['Effective'].split('-')])
        return cls(**d)

    @classmethod
    def iter(
            cls,
            table: Optional[Iterator[dict[str, str]]] = None,
            cache_dir: Optional[PathType] = None,
            log: Optional[logging.Logger] = None,
    ) -> Generator['Retirement', None, None]:
        """Read retirements from a table."""
        content = ''
        if not table:
            content = read_url(
                'sites/iso639-3/files/downloads/iso-639-3_Retirements.tab',
                cache_dir=cache_dir,
                log=log)
        for d in table or dsv.reader(content.splitlines(), dicts=True, delimiter='\t'):
            yield cls.from_dict(d)


CRStatusType = Literal['Rejected', 'Adopted', 'Pending', 'Partially Adopted', '']


@dataclasses.dataclass
class ChangeRequest:  # pylint: disable=R0902
    """A Change request."""
    CHANGE_TYPES = {  # map change types to a sort key
        'Create': 'z',
        'Merge': 'c',
        'Retire': 'a',
        'Split': 'b',
        'Update': 'y',
        '': '',
    }
    Status: CRStatusType  # pylint: disable=invalid-name
    Reference_Name: str  # pylint: disable=invalid-name
    Effective_Date: datetime.date  # pylint: disable=invalid-name
    Change_Type: str  # pylint: disable=invalid-name
    Change_Request_Number: str  # pylint: disable=invalid-name
    Region_Group: str  # pylint: disable=invalid-name
    Affected_Identifier: str  # pylint: disable=invalid-name
    Language_Family_Group: str  # pylint: disable=invalid-name

    def __post_init__(self):
        assert self.Status in get_args(CRStatusType)
        assert self.Change_Type in self.CHANGE_TYPES, self.Change_Type
        self.Change_Request_Number = str(self.Change_Request_Number) \
            if self.Change_Request_Number else None

    @classmethod
    def from_dict(cls, cr) -> Optional['ChangeRequest']:
        """Turn table row into ChangeRequest, provided it has an Effective Date."""
        d = {k.replace(' ', '_'): v for k, v in cr.items()}
        if d.get('Effective_Date'):
            d['Effective_Date'] = datetime.date(*[int(p) for p in d['Effective_Date'].split('-')])
            return cls(**d)
        return None  # pragma: no cover

    @property
    def url(self) -> str:
        """URL for the change request on the ISO-639 website."""
        return iso_639_3.BASE_URL + 'request/' + self.Change_Request_Number

    @property
    def year(self) -> str:
        """Year the change request was created."""
        return self.Change_Request_Number.split('-')[0]

    @property
    def pdf(self) -> str:
        """URL of the PDF with the cr details on the ISO-639 website."""
        return (f'{iso_639_3.BASE_URL}sites/iso639-3/files/change_requests/'
                f'{self.year}/{self.Change_Request_Number}.pdf')

    @classmethod
    def iter(
            cls,
            max_year: Optional[int] = None,
            cache_dir: Optional[PathType] = None,
            log: Optional[logging.Logger] = None,
    ) -> Generator['ChangeRequest', None, None]:
        """Read change requests from the website (or possibly from cached copies)."""
        path = "code_changes/change_request_index/data/{0}?" \
               "field_change_request_region_grp_tid=All&field_change_request_lf_group_tid=All&" \
               "field_change_instance_chnge_type_tid=All&field_change_request_act_status_tid=All&" \
               "items_per_page=100&page={1}"
        year, page = 2006, 0
        while year < (max_year or datetime.date.today().year):
            while True:
                i = 0
                tables = list(_iter_tables(
                    read_url(path.format(year, page), cache_dir=cache_dir, log=log)))
                if not tables:  # pragma: no cover
                    # For one year, the table seems to have exactly 100 rows.
                    print(f'no crs for {year}, page {page}')
                else:
                    for i, cr in enumerate(tables[0]):
                        res = ChangeRequest.from_dict(cr)
                        if res:
                            yield res
                if i < 99:
                    break
                page += 1  # pragma: no cover
            year += 1
            page = 0


def change_request_as_source(id_, rows, ref_ids) -> EntryType:
    """Format a change request as entry for a bibfile."""
    title = f"Change Request Number {id_}: "
    title += ", ".join(
        f"{r.Status.lower()} {r.Change_Type.lower()} [{r.Affected_Identifier}]"
        for r in sorted(
            rows,
            key=lambda cr: (ChangeRequest.CHANGE_TYPES[cr.Change_Type], cr.Affected_Identifier)))
    date = None
    for row in rows:
        if row.Effective_Date:
            if date:
                assert date == row.Effective_Date  # pragma: no cover
            else:
                date = row.Effective_Date
    if date:
        title += f' ({date.isoformat()})'
    fields = {
        'number': id_,
        'title': title,
        'howpublished': rows[0].url,
        'address': "Dallas",
        'author': "ISO 639-3 Registration Authority",
        'publisher': "SIL International",
        'url': rows[0].pdf,
        'year': rows[0].year,
        'hhtype': "overview",
        'lgcode': ', '.join(f"{r.Reference_Name} [{r.Affected_Identifier}]" for r in rows),
        'src': "iso6393",
    }
    if id_ in ref_ids and ref_ids[id_]:
        fields['glottolog_ref_id'] = ref_ids[id_]
    return id_, ('misc', fields)


def bibtex(api: 'Glottolog', log: logging.Logger, max_year: Optional[int] = None):
    """Create a BibTeX file listing records for each past ISO 639-3 change request.

    http://www-01.sil.org/iso639-3/chg_requests.asp?order=CR_Number&chg_status=past
    """
    bib = api.bibfiles['iso6393.bib']
    glottolog_ref_ids = bib.glottolog_ref_id_map

    entries: list[EntryType] = []

    with api.cache_dir(CACHE_DIR) as cache_dir:
        grouped = itertools.groupby(
            sorted(ChangeRequest.iter(max_year=max_year, cache_dir=cache_dir),
                   key=lambda cr: (cr.Change_Request_Number, cr.Affected_Identifier)),
            lambda cr: cr.Change_Request_Number)
        for id_, rows in grouped:
            entries.append(change_request_as_source(id_, list(rows), glottolog_ref_ids))

    save(entries, bib.fname, None)
    log.info('bibtex written to %s', bib.fname)
    return len(entries)


def _read_table(table):
    def _text(e):
        if e.find('span') is not None:
            return _text(e.find('span'))
        if e.find('a') is not None:
            return _text(e.find('a'))
        return e.text or ''

    d = ElementTree.fromstring(table)
    header = [e.text.strip() for e in d.findall('.//th')]
    for tr in d.find('tbody').findall('.//tr'):
        yield dict(zip(header, [normalize_whitespace(_text(e)) for e in tr.findall('.//td')]))


def _iter_tables(html):
    start, end = '<table ', '</table>'
    while start in html:
        html = html.split(start, 1)[1]
        table, html = html.split(end, 1)
        yield _read_table(start + table + end)


def code_details(
        code: str,
        cache_dir: Optional[pathlib.Path] = None,
        log: Optional[logging.Logger] = None,
) -> dict[str, str]:
    """Read additional code information from the SIL/ISO website."""
    res = {}
    try:
        for md in _iter_tables(read_url(f'code/{code}', cache_dir=cache_dir, log=log)):
            for row in md:
                for k, v in row.items():
                    if not res.get(k):
                        res[k] = v
    except:  # noqa: E722  # pylint: disable=W0702
        pass
    return res


def get_retirements(
        table: Optional[Iterator[dict[str, str]]] = None,
        max_year: Optional[int] = None,
        cache_dir: Optional[pathlib.Path] = None,
        log: Optional[logging.Logger] = None,
) -> list[Retirement]:
    """
    Get retirements augmented with change request info.
    """
    # retired iso_codes
    rets = list(Retirement.iter(table=table, cache_dir=cache_dir, log=log))

    # latest adopted change request affecting each iso_code
    crs = (
        r for r in ChangeRequest.iter(max_year=max_year, cache_dir=cache_dir, log=log)
        if r.Status == 'Adopted')
    crs = sorted(
        crs, key=lambda r: (r.Affected_Identifier, r.Effective_Date or datetime.date.today()))
    crs = itertools.groupby(crs, lambda r: r.Affected_Identifier)
    crs = {id_: list(grp)[-1] for id_, grp in crs}

    # left join
    for ret in rets:
        ret.cr = crs.get(ret.Id)

    # lcq seeems to be listed as retired by accident.
    # See https://github.com/glottolog/pyglottolog/issues/1
    rets = [ret for ret in rets if ret.Id != 'lcq']

    # fill Change_To from Ret_Remedy for splits and make it a list for others
    assert all(
        bool(r.Change_To) == (r.Ret_Reason not in (RetReason.S, RetReason.N, None)) for r in rets)
    assert all(bool(r.Ret_Remedy) == (r.Ret_Reason == RetReason.S) for r in rets)
    iso = re.compile(r'\[([a-z]{3})]')
    for r in rets:
        if r.Ret_Reason == RetReason.S:
            r.Change_To = iso.findall(r.Ret_Remedy)
        else:
            r.Change_To = [r.Change_To] if r.Change_To else []

    for r in rets:
        if not r.Ret_Remedy:
            r.Ret_Remedy = code_details(r.Id, cache_dir=cache_dir, log=log).get('Retirement Remedy')

    return rets


def retirements(api: 'Glottolog', log: logging.Logger, max_year: Optional[int] = None):
    """
    Add info about ISO retirements to languoids.
    """
    fields = [
        ('Id', 'code', None),
        ('Ref_Name', 'name', None),
        ('Effective', 'effective', None),
        ('Ret_Reason', 'reason', lambda v: v.value),
        ('Change_To', 'change_to', None),
        ('Ret_Remedy', 'remedy', None),
    ]
    log.info('read languoid info')
    iso2lang = {lang.iso: lang for lang in api.languoids() if lang.iso}
    log.info('retrieve retirement info %s', api.iso)
    with api.cache_dir(CACHE_DIR) as cache_dir:
        rets: list[Retirement] = get_retirements(
            table=api.iso._tables['Retirements'],  # pylint: disable=W0212
            cache_dir=cache_dir,
            log=log,
            max_year=max_year)
    for r in rets:
        lang = iso2lang.get(r.Id)
        if lang is None:
            print(f'--- Missing retired ISO code: {r.Id}')
            continue
        for iso in r.Change_To:
            if iso not in iso2lang:
                print(f'+++ Missing change_to ISO code: {iso}')
        for f, option, conv in fields:
            v = getattr(r, f)
            if conv:
                v = conv(v)
            lang.cfg.set('iso_retirement', option, v)
        if r.cr and r.cr.Change_Request_Number:
            lang.cfg.set('iso_retirement', 'change_request', r.cr.Change_Request_Number)
        lang.write_info()


def check_coverage(
        iso: iso_639_3.ISO,
        iso_in_gl: 'LanguoidMapType',
        iso_splits: list['Languoid'],
) -> Generator[LogMessageType, None, None]:
    """Report isocodes not associated with any Glottolog languoid."""
    changed_to = set(itertools.chain(*[code.change_to for code in iso.retirements]))
    for code in sorted(iso.languages):
        if code.type == 'Individual/Living':
            if code not in changed_to:
                if code.code not in iso_in_gl:
                    yield 'info', repr(code), 'missing'
    for lang in iso_splits:
        isocode = iso[lang.iso]
        missing = [s.code for s in isocode.change_to if s.code not in iso_in_gl]
        if missing:
            yield 'warn', lang, f"{repr(isocode)} missing new codes: {', '.join(missing)}"


def check_lang(
        api: 'Glottolog',
        isocode: iso_639_3.Code,
        lang: 'Languoid',
        iso_splits: list['Languoid'] = None,
) -> Optional[LogMessageType]:
    """
    Check for retired isocodes associated with languoids.
    Return constituents of a log message for cases we want to flag.
    """
    iso_splits = [] if iso_splits is None else iso_splits
    fid = lang.lineage[0][1] if lang.lineage else None
    if isocode.is_retired and \
            fid not in [api.language_types.bookkeeping.pseudo_family_id,
                        api.language_types.unattested.pseudo_family_id]:
        # A retired isocode associated with a "regular" languoid.
        if isocode.type == 'Retirement/split':
            iso_splits.append(lang)
        else:
            if isocode.type == 'Retirement/merge' and lang.level == api.languoid_levels.dialect:
                # Retired isocodes that are mergers but show up as dialects in Glottolog: This is
                # desired behaviour and shouldn't generate a warning in glottolog check
                pass
            else:
                msg = repr(isocode)
                level = 'info'
                if len(isocode.change_to) == 1:
                    level = 'warn'
                    msg += f' changed to [{isocode.change_to[0].code}]'
                return level, lang, msg
    return None  # pragma: no cover
