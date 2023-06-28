import re
import html
import pathlib
import tempfile
import subprocess

import requests
from clldutils.source import Source
from clldutils.oaipmh import iter_records
try:
    from bs4 import BeautifulSoup as bs  # noqa: N813
except ImportError:  # pragma: no cover
    bs = None

OAIPMH_URL = 'https://account.lddjournal.org/index.php/uv1-j-ldd/oai'


def download(bibfile, log):  # pragma: no cover
    fname = scrape(pathlib.Path(tempfile.gettempdir()) / 'elpub.bib')
    bibfile.update(fname, log=log)
    bibfile.check(log)
    fname.unlink()


def iter_language_codes_from_pdf(url):  # pragma: no cover
    """
    Parse the associated language codes from the PDF.
    """
    iso = None
    gcodes = False

    url = bs(requests.get(url).text, features='lxml').find('a', class_='download')['href']

    with tempfile.TemporaryDirectory() as d:
        pdf = pathlib.Path(d) / '{}.pdf'.format(url.split('/')[-1])
        txt = pathlib.Path(d) / url.split('/')[-1].replace('.pdf', '.txt')
        # Download the PDF
        pdf.write_bytes(requests.get(url).content)
        # Run pdftotext
        subprocess.check_call(['pdftotext', str(pdf), str(txt)], stderr=subprocess.DEVNULL)
        # Identify the codes - which are assumed to appear in a table,
        # which is extracted as "one cell per line" so can be identified
        # by regex applied to the complete line.
        for line in txt.read_text(encoding='utf8').split('\n'):
            line = line.strip()
            if re.match('[a-z]{4}[0-9]{4}$', line):
                gcodes = True
                yield line
            m = re.match(r'Glottolog Code:\s*(?P<code>[a-z]{4}[0-9]{4})', line)
            if m:
                gcodes = True
                yield m.group('code')
            if re.match('([a-z]{3}|[A-Z]{3})$', line):
                iso = line.lower()
            m = re.match(r'ISO 639-3 Code:\s*(?P<code>[a-z]{3}|[A-Z]{3})$', line)
            if m:
                iso = m.group('code')
    if iso and not gcodes:
        yield iso


def scrape_article(record, hhtype):  # pragma: no cover
    doi = None
    for id_ in record.oai_dc_metadata['identifier']:
        if id_.startswith('10.2'):
            doi = id_
            break
    else:
        raise ValueError('no DOI found in dc:identifier')
    pdf_url = record.oai_dc_metadata['relation'][0]
    md = {
        'title': html.unescape(record.oai_dc_metadata['title'][0]),
        'author': ' and '.join(record.oai_dc_metadata['creator']),
        'hhtype': hhtype,
        'journal': 'Language Documentation and Description',
        'url': 'https://doi.org/' + doi,
        'abstract': html.unescape(record.oai_dc_metadata['description'][0]),
        'lgcode': '; '.join('[{}]'.format(code) for code in iter_language_codes_from_pdf(pdf_url)),
        'subject': '; '.join(record.oai_dc_metadata.get('subject', [])),
    }
    source_pattern = re.compile(
        r'Language Documentation and Description; Vol. (?P<volume>[0-9]+) '
        r'(No\. (?P<number>[0-9]+) )?\((?P<year>[0-9]+)\); (?P<pages>[0-9\-]+)')
    for source in record.oai_dc_metadata['source']:
        m = source_pattern.match(source)
        if m:
            md.update(m.groupdict())
            break
    else:
        if record.oai_dc_metadata['source']:
            raise ValueError('No matching dc:source "{}" found!'.format(record.oai_dc_metadata['source']))
    return Source('article', doi.split('/')[-1].replace('.', ''), **md)


def scrape(fname):  # pragma: no cover
    records = []
    for set_ in ['Snapshots', 'Contexts']:
        for record in iter_records(OAIPMH_URL, set_='uv1-j-ldd:{}'.format(set_)):
            if record.oai_dc_metadata:
                records.append(scrape_article(record, 'overview'))
    fname.write_text(
        '\n'.join([r.bibtex() for r in sorted(
            records, key=lambda r: int(r.id.replace('ldd', '')))]), encoding='utf8')
    return fname
