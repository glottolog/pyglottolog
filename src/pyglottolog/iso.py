import re
import hashlib
import pathlib
import datetime
import itertools
from xml.etree import ElementTree

import attr
from clldutils import iso_639_3
from csvw import dsv

from .references.bibtex import save

ISO_CODE_PATTERN = re.compile('[a-z]{3}$')
CACHE_DIR = 'iso_639_3_cache'


def read_url(path, cache_dir=None, log=None):
    """
    Delegate scraping to clldutils, since nowadays this requires tweaking the user agent as well.
    """
    if cache_dir:
        cache_dir = pathlib.Path(cache_dir)
        if log:  # pragma: no cover
            log.debug('retrieving {0} ...'.format(path))
        fpath = cache_dir / hashlib.md5(path.encode('utf8')).hexdigest()
        if not fpath.exists():
            with iso_639_3._open(path) as fp:
                fpath.write_text(fp.read().decode('utf8'), encoding='utf8')
        else:  # pragma: no cover
            if log:
                log.debug('... from cache {0}'.format(fpath))
        return fpath.read_text(encoding='utf8')

    with iso_639_3._open(path) as fp:
        return fp.read().decode('utf8')


def valid_iso_code(instance, attr, value):
    if not ISO_CODE_PATTERN.match(value):
        raise ValueError('invalid ISO code in {0}: {1}'.format(attr.name, value))


def normalize_whitespace(s):
    return re.sub(r'\s+', ' ', s).strip()


@attr.s
class Retirement(object):
    RET_REASON = {  # http://www-01.sil.org/iso639-3/download.asp#retiredDownloads
        'C': 'change',
        'D': 'duplicate',
        'N': 'non-existent',
        'S': 'split',
        'M': 'merge',
    }
    Id = attr.ib(validator=valid_iso_code)
    Ref_Name = attr.ib()
    Ret_Reason = attr.ib(converter=lambda v: Retirement.RET_REASON.get(v))
    Change_To = attr.ib(
        converter=lambda v: v or None,
        validator=attr.validators.optional(valid_iso_code))
    Ret_Remedy = attr.ib(converter=normalize_whitespace)
    Effective = attr.ib(
        converter=lambda v: datetime.date(*[int(p) for p in v.split('-')]) if v else None)
    cr = attr.ib(default=None)

    @classmethod
    def iter(cls, table=None, cache_dir=None, log=None):
        content = read_url(
            'sites/iso639-3/files/downloads/iso-639-3_Retirements.tab',
            cache_dir=cache_dir,
            log=log)
        for d in table or dsv.reader(content.splitlines(), dicts=True, delimiter='\t'):
            yield cls(**d)


@attr.s
class ChangeRequest(object):
    CHANGE_TYPES = {  # map change types to a sort key
        'Create': 'z',
        'Merge': 'c',
        'Retire': 'a',
        'Split': 'b',
        'Update': 'y'
    }
    Status = attr.ib(
        validator=attr.validators.in_(['Rejected', 'Adopted', 'Pending', 'Partially Adopted']))
    Reference_Name = attr.ib()
    Effective_Date = attr.ib(
        converter=lambda v: datetime.date(*[int(p) for p in v.split('-')]) if v else None)
    Change_Type = attr.ib(validator=attr.validators.in_(list(CHANGE_TYPES.keys())))
    Change_Request_Number = attr.ib(converter=lambda v: str(v) if v else None)
    Region_Group = attr.ib()
    Affected_Identifier = attr.ib()
    Language_Family_Group = attr.ib()

    @property
    def url(self):
        return iso_639_3.BASE_URL + 'request/' + self.Change_Request_Number

    @property
    def year(self):
        return self.Change_Request_Number.split('-')[0]

    @property
    def pdf(self):
        return '{0}sites/iso639-3/files/change_requests/{1}/{2}.pdf'.format(
            iso_639_3.BASE_URL, self.year, self.Change_Request_Number)

    @classmethod
    def iter(cls, max_year=None, cache_dir=None, log=None):
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
                    print('no crs for {}, page {}'.format(year, page))
                else:
                    for i, cr in enumerate(tables[0]):
                        yield cls(**{k.replace(' ', '_'): v for k, v in cr.items()})
                if i < 99:
                    break
                page += 1  # pragma: no cover
            year += 1
            page = 0


def change_request_as_source(id_, rows, ref_ids):
    title = "Change Request Number {0}: ".format(id_)
    title += ", ".join(
        "{0} {1} [{2}]".format(r.Status.lower(), r.Change_Type.lower(), r.Affected_Identifier)
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
        title += ' ({0})'.format(date.isoformat())
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
        'lgcode': ', '.join(
            "{0} [{1}]".format(r.Reference_Name, r.Affected_Identifier) for r in rows),
        'src': "iso6393",
    }
    if id_ in ref_ids and ref_ids[id_]:
        fields['glottolog_ref_id'] = ref_ids[id_]
    return id_, ('misc', fields)


def bibtex(api, log, max_year=None):
    """Create a BibTeX file listing records for each past ISO 639-3 change request.

    http://www-01.sil.org/iso639-3/chg_requests.asp?order=CR_Number&chg_status=past
    """
    bib = api.bibfiles['iso6393.bib']
    glottolog_ref_ids = bib.glottolog_ref_id_map

    entries = []

    with api.cache_dir(CACHE_DIR) as cache_dir:
        grouped = itertools.groupby(
            sorted(ChangeRequest.iter(max_year=max_year, cache_dir=cache_dir),
                   key=lambda cr: (cr.Change_Request_Number, cr.Affected_Identifier)),
            lambda cr: cr.Change_Request_Number)
        for id_, rows in grouped:
            entries.append(change_request_as_source(id_, list(rows), glottolog_ref_ids))

    save(entries, bib.fname, None)
    log.info('bibtex written to {0}'.format(bib.fname))
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


def code_details(code, cache_dir=None, log=None):
    res = {}
    try:
        for md in _iter_tables(read_url('code/{0}'.format(code), cache_dir=cache_dir, log=log)):
            for row in md:
                for k, v in row.items():
                    if not res.get(k):
                        res[k] = v
    except:  # noqa: E722
        pass
    return res


def get_retirements(table=None, max_year=None, cache_dir=None, log=None):
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
    # See https://github.com/clld/pyglottolog/issues/1
    rets = [ret for ret in rets if ret.Id != 'lcq']

    # fill Change_To from Ret_Remedy for splits and make it a list for others
    assert all(
        bool(r.Change_To) == (r.Ret_Reason not in ('split', 'non-existent', None)) for r in rets)
    assert all(bool(r.Ret_Remedy) == (r.Ret_Reason == 'split') for r in rets)
    iso = re.compile(r'\[([a-z]{3})\]')
    for r in rets:
        if r.Ret_Reason == 'split':
            r.Change_To = iso.findall(r.Ret_Remedy)
        else:
            r.Change_To = [r.Change_To] if r.Change_To else []

    for r in rets:
        if not r.Ret_Remedy:
            r.Ret_Remedy = code_details(r.Id, cache_dir=cache_dir, log=log).get('Retirement Remedy')

    return rets


def retirements(api, log, max_year=None):
    fields = [
        ('Id', 'code'),
        ('Ref_Name', 'name'),
        ('Effective', 'effective'),
        ('Ret_Reason', 'reason'),
        ('Change_To', 'change_to'),
        ('Ret_Remedy', 'remedy'),
    ]
    log.info('read languoid info')
    iso2lang = {lang.iso: lang for lang in api.languoids() if lang.iso}
    log.info('retrieve retirement info {0}'.format(api.iso))
    with api.cache_dir(CACHE_DIR) as cache_dir:
        rets = get_retirements(
            table=api.iso._tables['Retirements'], cache_dir=cache_dir, log=log, max_year=max_year)
    for r in rets:
        lang = iso2lang.get(r.Id)
        if lang is None:
            print('--- Missing retired ISO code: {}'.format(r.Id))
            continue
        for iso in r.Change_To:
            if iso not in iso2lang:
                print('+++ Missing change_to ISO code: {}'.format(iso))
        for f, option in fields:
            lang.cfg.set('iso_retirement', option, getattr(r, f))
        if r.cr and r.cr.Change_Request_Number:
            lang.cfg.set('iso_retirement', 'change_request', r.cr.Change_Request_Number)
        lang.write_info()


def check_coverage(iso, iso_in_gl, iso_splits):
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
            yield (
                'warn',
                lang,
                '{0} missing new codes: {1}'.format(repr(isocode), ', '.join(missing)),
            )


def check_lang(api, isocode, lang, iso_splits=None):
    iso_splits = [] if iso_splits is None else iso_splits
    fid = lang.lineage[0][1] if lang.lineage else None
    if isocode.is_retired and \
            fid not in [api.language_types.bookkeeping.pseudo_family_id,
                        api.language_types.unattested.pseudo_family_id]:
        if isocode.type == 'Retirement/split':
            iso_splits.append(lang)
        else:
            if isocode.type == 'Retirement/merge' and lang.level == api.languoid_levels.dialect:
                # See https://github.com/clld/pyglottolog/issues/2
                pass
            else:
                msg = repr(isocode)
                level = 'info'
                if len(isocode.change_to) == 1:
                    level = 'warn'
                    msg += ' changed to [%s]' % isocode.change_to[0].code
                return level, lang, msg
