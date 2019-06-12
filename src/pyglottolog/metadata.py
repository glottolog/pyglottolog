# coding: utf8
from __future__ import unicode_literals

from six.moves import html_entities

from nameparser import HumanName
from markdown import markdown
from clldutils.path import read_text
from clldutils.jsonlib import dump


URL = 'https://glottolog.org'
EDITORS = {
    'Harald Hammarström': ('University Uppsala', None),
    'Robert Forkel': (
        'Max Planck Institute for the Science of Human History', '0000-0003-1081-086X'),
    'Martin Haspelmath': (
        'Max Planck Institute for the Science of Human History', '0000-0003-2100-8493'),
}


def to_html(text):
    c2n = html_entities.codepoint2name
    text = text.replace('&', '&amp;')
    text = ''.join('&{0};'.format(
        c2n[ord(c)]) if ord(c) > 128 and ord(c) in c2n else c for c in text)
    return markdown(text.replace(URL, '[{0}]({0})'.format(URL)))


def read_editors(repos):
    res = []
    in_editors, in_table = False, False
    for line in read_text(repos.path('CONTRIBUTORS.md')).split('\n'):
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


def editor_to_dict(n):
    res = {'name': n}
    affiliation, orcid = EDITORS.get(n, (None, None))
    if affiliation:
        res['affiliation'] = affiliation
    if orcid:
        res['orcid'] = orcid
    return res


def prepare_release(repos, version):
    for v, year, editors in read_editors(repos):
        if v == version:
            break
    else:  # pragma: no cover
        raise ValueError('Add version to CONTRIBUTORS.md first!')

    citation = """\
{0}. {1}.
Glottolog {2}.
Jena: Max Planck Institute for the Science of Human History.
(Available online at https://glottolog.org)
""".format(' & '.join('{0.last}, {0.first}'.format(HumanName(e)) for e in editors), year, version)
    dump(
        {
            "title": "glottolog/glottolog: Glottolog database {0}".format(version),
            "description": to_html(citation),
            "license": {"id": "CC-BY-4.0"},
            "keywords": ["linguistics"],
            "upload_type": "dataset",
            "communities": [{"identifier": "clld"}],
            "creators": [editor_to_dict(n) for n in editors],
            "access_right": "open"
        },
        repos.path('.zenodo.json'),
        indent=4)
