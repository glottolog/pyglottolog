import re
import pathlib
import tempfile
import subprocess

import requests
from clldutils.source import Source
try:
    from bs4 import BeautifulSoup as bs  # noqa: N813
except ImportError:  # pragma: no cover
    bs = None

LS_INDEX = 'http://www.elpublishing.org/language-snapshots'

LC_INDEX = 'http://www.elpublishing.org/language-contexts'


def download(bibfile, log):  # pragma: no cover
    fname = scrape(pathlib.Path(tempfile.gettempdir()) / 'elpub.bib')
    bibfile.update(fname, log=log)
    bibfile.check(log)
    fname.unlink()


def get(url):  # pragma: no cover
    # Some user agents seem to be rejected
    return requests.get(url, headers={'User-Agent': 'scrapy'})


def get_html(url):  # pragma: no cover
    return bs(get(url).text, 'html5lib')


def get_language_name(title):  # pragma: no cover
    if 'Contexts' in title and (':' in title):
        return title.split(':', maxsplit=1)[-1].strip()
    return title.split(')')[0] + ')'


def language_code_from_pdf(url):  # pragma: no cover
    """
    Parse the associated language code from the PDF.
    """
    iso = None

    with tempfile.TemporaryDirectory() as d:
        pdf = pathlib.Path(d) / url.split('/')[-1]
        txt = pathlib.Path(d) / url.split('/')[-1].replace('.pdf', '.txt')
        # Download the PDF
        with pdf.open('wb') as f:
            f.write(get(url).content)
        # Run pdftotext
        subprocess.check_call(
            ['pdftotext', str(pdf), str(txt)],
            stderr=subprocess.DEVNULL,
        )
        # Identify the code - which is assumed to appear in a table,
        # which is extracted as "one cell per line" so can be identified
        # by regex applied to the complete line.
        for line in txt.read_text(encoding='utf8').split('\n'):
            line = line.strip()
            if re.match('[a-z]{4}[0-9]{4}$', line):
                return line
            m = re.match(r'Glottolog Code:\s*(?P<code>[a-z]{4}[0-9]{4})', line)
            if m:
                return m.group('code')
            if re.match('([a-z]{3}|[A-Z]{3})$', line):
                iso = line.lower()
            m = re.match(r'ISO 639-3 Code:\s*(?P<code>[a-z]{3}|[A-Z]{3})$', line)
            if m:
                iso = m.group('code')
    return iso


def scrape_article(url, hhtype):  # pragma: no cover
    html = get_html(url)
    md = {
        'title': html.find('h3').text,
        'author': [],
        'hhtype': hhtype,
        'journal': 'Language Documentation and Description',
        'url': url,
    }
    pdf_url = None
    for div in html.find_all('div'):
        if div.text.startswith('Link to item:'):
            pdf_url = div.find('a')['href']
            assert pdf_url.endswith('.pdf')
            code = language_code_from_pdf(pdf_url)
            if code:
                md['lgcode'] = '{} [{}]'.format(get_language_name(md['title']), code)
        if div.find('span') and div.find('span').text.startswith('Pages'):
            md['pages'] = div.find('div').text
        if div.text.startswith('Date: '):
            md['year'] = div.text.split(':')[1].strip()
    for td in html.find_all('td'):
        link = td.find('a')
        if link and link.attrs.get('href').startswith('/authorpage'):
            md['author'].append(link.text)
    assert pdf_url
    match = re.search(r'/ldd(?P<volume>[0-9]+)_[0-9]+\.pdf', pdf_url)
    md.update(match.groupdict())
    md['author'] = ' and '.join(md['author'])
    return Source('article', url.split('/')[-1], **md)


def scrape(fname):  # pragma: no cover
    records = []
    index = get_html(LS_INDEX)
    for td in index.find_all('td'):
        if 'title' in td.attrs.get('class', []):
            link = td.find('a')
            records.append(scrape_article(link['href'], 'overview'))
    index = get_html(LC_INDEX)
    for link in index.find_all('a'):
        if '/itempage/' in link.attrs.get('href', ''):
            records.append(scrape_article(link['href'], 'overview'))
    fname.write_text(
        '\n'.join([r.bibtex() for r in sorted(records, key=lambda r: int(r.id))]), encoding='utf8')
    return fname
