import re
import pathlib
import tempfile
import urllib.parse

import pycountry
import requests
from lxml.etree import fromstring, HTMLParser
from pycldf.sources import Source

INDEX_URL = "https://www.lddjournal.org/articles/"
URLS = {
    'contexts':
        '{}?date_published__date__gte=&date_published__date__lte=&section__pk=55'.format(INDEX_URL),
    'snapshots':
        '{}?date_published__date__gte=&date_published__date__lte=&section__pk=54'.format(INDEX_URL),
}


def get(url, cache, series=None):  # pragma: no cover
    parsed = urllib.parse.urlparse(url)
    if parsed.path.endswith('articles/'):
        assert series
        fname = 'index_{}.html'.format(series)
    else:
        m = re.fullmatch(r'/article/(pub)?id/(?P<aid>[0-9]+)/', parsed.path)
        if m:
            fname = '{}.html'.format(m.group('aid'))
        else:
            m = re.fullmatch(r'/article/id/(?P<aid>[0-9]+)/download/xml/', parsed.path)
            if m:
                fname = '{}.xml'.format(m.group('aid'))
            else:
                raise ValueError(url)
    p = cache / fname
    if fname.startswith('index') or not p.exists():
        p.write_text(requests.get(url).text, encoding='utf8')
    if p.suffix == '.html':
        return fromstring(p.read_text(encoding='utf8'), parser=HTMLParser())
    return fromstring(p.read_bytes())


def iter_items(repos):  # pragma: no cover
    cache = repos.repos / 'build' / 'elpub'
    if not cache.exists():
        cache.mkdir()

    for series, url in URLS.items():
        for div in get(url, cache, series).xpath('.//div'):
            if 'class' in div.attrib and div.attrib['class'] == 'box article':
                xml = None
                metas = get(div.xpath('a')[0].attrib['href'], cache).xpath('head/meta')
                for meta in metas:
                    if meta.attrib.get('name') == 'citation_xml_url':
                        xml = get(meta.attrib['content'], cache)

                        break
                yield scrape_article(
                    series,
                    [(m.attrib['name'], m.attrib['content']) for m in metas if 'name' in m.attrib],
                    xml)


def download(bibfile, log, repos):  # pragma: no cover
    old, new = [], []
    for e in bibfile.iterentries():
        old.append(e.key)
    for item in iter_items(repos):
        if item.id not in old:
            new.append(item)

    if new:
        fname = pathlib.Path(tempfile.gettempdir()) / 'elpub.bib'
        fname.write_text(
            '\n'.join([r.bibtex() for r in sorted(
                new, key=lambda r: int(r.id.replace('ldd', '')))]), encoding='utf8')

        bibfile.update(fname, log=log, keep_old=True)
        bibfile.check(log)
        fname.unlink()


def scrape_article(series, metas, xml):  # pragma: no cover
    meta2bibtex = {
        'citation_journal_title': ('journal', False, None),
        'citation_issn': ('issn', False, None),
        'citation_author': ('author', True, None),
        'citation_title': ('title', False, None),
        'citation_publication_date': ('year', False, lambda s: s.split('-')[0]),
        'citation_volume': ('volume', False, None),
        'citation_issue': ('number', False, None),
        'citation_doi': ('doi', False, None),
    }
    md = {'hhtype': 'overview'}
    for name, content in metas:
        if name in meta2bibtex:
            bname, mult, conv = meta2bibtex[name]
            content = conv(content) if conv else content
            if not mult:
                md[bname] = content
            else:
                if bname in md:
                    md[bname].append(content)
                else:
                    md[bname] = [content]
    md['author'] = ' and '.join(md['author'])
    md['url'] = 'https://doi.org/{}'.format(md['doi'])
    if xml is not None:
        md.update(parse_xml(xml))
    return Source('article', md['doi'].split('/')[-1].replace('.', ''), **md)


def parse_xml(article):  # pragma: no cover
    from lxml.etree import tostring
    inlg = pycountry.languages.get(
        alpha_2=article.attrib['{http://www.w3.org/XML/1998/namespace}lang'])
    abstract = article.xpath('.//{}abstract'.format('trans-' if inlg.alpha_2 != 'en' else ''))[0]
    if '{http://www.w3.org/XML/1998/namespace}lang' in abstract.attrib:
        assert abstract.attrib['{http://www.w3.org/XML/1998/namespace}lang'] == 'en'
    try:
        res = {
        'inlg': '{} [{}]'.format(inlg.name, inlg.alpha_3),
        'abstract': '\n'.join(re.sub(r'\s+', ' ', p.text) for p in abstract.xpath('p') if p.text),
        'subject': '; '.join(kw.text for kw in article.xpath('.//kwd-group/kwd') if kw.text),
        }
    except:
        print(tostring(article).decode('utf8'))
        raise
    props = []
    for e in article.xpath('body/*'):
        if e.tag == 'sec':
            break
        props.append(e)
    for e in props:  # table-wrap or some p
        m = re.search(r'(?P<gc>[a-z]{4}[0-9]{4})', ''.join(e.itertext()))
        if m:
            res['lgcode'] = '[{}]'.format(m.group('gc'))
            break
    return res
