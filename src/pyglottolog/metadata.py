"""
Managing metadata for Glottolog editions.
"""
from html import entities as html_entities
from typing import TYPE_CHECKING, TypedDict, Optional

from packaging import version
from nameparser import HumanName
from markdown import markdown
from clldutils.markup import iter_markdown_tables
from clldutils.jsonlib import dump

from pyglottolog import config

if TYPE_CHECKING:
    from pyglottolog import Glottolog


class Edition(TypedDict):
    """Info about a Glottolog edition, as given in CONTRIBUTORS.md"""
    version: str
    year: str
    editors: list[str]


def to_html(text: str, url: str) -> str:
    """
    >>> to_html('See http://example.com', 'http://example.com')
    '<p>See <a href="http://example.com">http://example.com</a></p>'
    """
    c2n = html_entities.codepoint2name
    text = text.replace('&', '&amp;')
    text = ''.join('&{0};'.format(
        c2n[ord(c)]) if ord(c) > 128 and ord(c) in c2n else c for c in text)
    return markdown(text.replace(url, f'[{url}]({url})'))


def read_editions(repos: 'Glottolog') -> list[Edition]:
    """Get list o editions, current first."""
    head, rows = next(iter_markdown_tables(
        repos.path('CONTRIBUTORS.md').read_text(encoding='utf8')))
    res = []
    for row in rows:
        row = dict(zip([c.lower() for c in head], row))
        row['editors'] = [n.strip() for n in row['editors'].split('&')]
        res.append(row)

    return sorted(res, key=lambda d: version.parse(d['version']), reverse=True)


def editor_to_dict(name: str, editors: config.Editors) -> dict[str, str]:
    """Info about a current Glottolog editor identified by name."""
    res = {'name': name}
    for e in editors.values():
        if e.name == name:
            assert e.current, f'{name} is not marked as current editor'
            if e.affiliation:
                res['affiliation'] = e.affiliation
            if e.orcid:
                res['orcid'] = e.orcid
            break
    return res


def get_edition(  # pylint: disable=W0621
        repos: 'Glottolog',
        version: Optional[str] = None) -> Edition:
    """Get the edition matching version - or implicitly the version in the config."""
    version = version or getattr(repos.publication.zenodo, 'version', '0.0.1.dev0')
    for edition in read_editions(repos):
        if edition['version'] == version:
            return edition
    raise ValueError(f'Add version {version} to CONTRIBUTORS.md first!')  # pragma: no cover


def citation(repos, edition=None, version=None) -> str:  # pylint: disable=W0621
    """A formatted citation for an edition."""
    edition = edition or get_edition(repos, version=version)
    editors = [f'{n.last}, {n.first}' for n in [HumanName(e) for e in edition['editors']]]
    return (f"{' & '.join(editors)}. {edition['year']}. "
            f"{repos.publication.web.name} {edition['version']}. "
            f"{repos.publication.publisher.place}: {repos.publication.publisher.name}. "
            f"(Available online at {repos.publication.web.url})")


def prepare_release(repos, version=None) -> str:  # pylint: disable=W0621
    """Write metadata for Zenodo and return a citation."""
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
