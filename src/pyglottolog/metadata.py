from html import entities as html_entities
import pkg_resources

from nameparser import HumanName
from markdown import markdown
from clldutils.markup import iter_markdown_tables
from clldutils.jsonlib import dump


def to_html(text, url):
    c2n = html_entities.codepoint2name
    text = text.replace('&', '&amp;')
    text = ''.join('&{0};'.format(
        c2n[ord(c)]) if ord(c) > 128 and ord(c) in c2n else c for c in text)
    return markdown(text.replace(url, '[{0}]({0})'.format(url)))


def read_editions(repos):
    head, rows = next(iter_markdown_tables(
        repos.path('CONTRIBUTORS.md').read_text(encoding='utf8')))
    res = []
    for row in rows:
        row = dict(zip([c.lower() for c in head], row))
        row['editors'] = [n.strip() for n in row['editors'].split('&')]
        res.append(row)

    return sorted(res, key=lambda d: pkg_resources.parse_version(d['version']), reverse=True)


def editor_to_dict(n, editors):
    res = {'name': n}
    for e in editors.values():
        if e.name == n:
            assert e.current, '{} is not marked as current editor'.format(n)
            if e.affiliation:
                res['affiliation'] = e.affiliation
            if e.orcid:
                res['orcid'] = e.orcid
            break
    return res


def get_edition(repos, version=None):
    version = version or getattr(repos.publication.zenodo, 'version', '0.0.1.dev0')
    for edition in read_editions(repos):
        if edition['version'] == version:
            return edition
    raise ValueError('Add version {} to CONTRIBUTORS.md first!'.format(version))  # pragma: no cover


def citation(repos, edition=None, version=None):
    edition = edition or get_edition(repos, version=version)
    return "{0}. {1}. {2} {3}. {4}: {5}. (Available online at {6})".format(
        ' & '.join('{0.last}, {0.first}'.format(HumanName(e)) for e in edition['editors']),
        edition['year'],
        repos.publication.web.name,
        edition['version'],
        repos.publication.publisher.place,
        repos.publication.publisher.name,
        repos.publication.web.url,
    )


def prepare_release(repos, version=None):
    edition = get_edition(repos, version=version)
    cit = citation(repos, edition=edition, version=version)
    dump(
        {
            "title": repos.publication.zenodo.title_format.format(edition['version']),
            "description": to_html(cit, repos.publication.web.url),
            "license": {"id": repos.publication.zenodo.license_id},
            "keywords": repos.publication.zenodo.keywords.split(),
            "communities": [
                {"identifier": cid} for cid in repos.publication.zenodo.communities.split()],
            "creators": [editor_to_dict(n, repos.editors) for n in edition['editors']],
            "access_right": "open",
            "upload_type": "dataset",
        },
        repos.path('.zenodo.json'),
        indent=4)
    return cit
