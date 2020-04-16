from html import entities as html_entities

from nameparser import HumanName
from markdown import markdown
from clldutils.jsonlib import dump


def to_html(text, url):
    c2n = html_entities.codepoint2name
    text = text.replace('&', '&amp;')
    text = ''.join('&{0};'.format(
        c2n[ord(c)]) if ord(c) > 128 and ord(c) in c2n else c for c in text)
    return markdown(text.replace(url, '[{0}]({0})'.format(url)))


def read_editors(repos):
    res = []
    in_editors, in_table = False, False
    for line in repos.path('CONTRIBUTORS.md').read_text(encoding='utf8').split('\n'):
        line = line.strip()
        if line.startswith('##'):
            if in_editors:
                in_editors = False
            elif line.endswith('Editors'):
                in_editors = True
            continue

        if line.startswith('---'):
            in_table = True
            continue

        if in_editors and in_table and line.strip():
            row = [m.strip() for m in line.split('|')]
            row[2] = [n.strip() for n in row[2].split('&')]
            res.append(row)
    return sorted(res, key=lambda t: tuple(map(int, t[0].split('.'))), reverse=True)


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


def prepare_release(repos, version):
    for v, year, editors in read_editors(repos):
        if v == version:
            break
    else:  # pragma: no cover
        raise ValueError('Add version to CONTRIBUTORS.md first!')

    citation = "{0}. {1}. {2} {3}. {4}: {5}. (Available online at {6})".format(
        ' & '.join('{0.last}, {0.first}'.format(HumanName(e)) for e in editors),
        year,
        repos.publication.web.name,
        version,
        repos.publication.publisher.place,
        repos.publication.publisher.name,
        repos.publication.web.url,
    )
    dump(
        {
            "title": repos.publication.zenodo.title_format.format(version),
            "description": to_html(citation, repos.publication.web.url),
            "license": {"id": repos.publication.zenodo.license_id},
            "keywords": repos.publication.zenodo.keywords.split(),
            "communities": [
                {"identifier": cid} for cid in repos.publication.zenodo.communities.split()],
            "creators": [editor_to_dict(n, repos.editors) for n in editors],
            "access_right": "open"
        },
        repos.path('.zenodo.json'),
        indent=4)
    return citation
