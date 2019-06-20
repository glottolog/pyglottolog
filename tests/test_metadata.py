from clldutils.jsonlib import load

from pyglottolog.metadata import prepare_release


def test_read_editors(api_copy):
    prepare_release(api_copy, '3.3')
    zenodo = load(api_copy.path('.zenodo.json'))
    assert zenodo['creators'][1]['affiliation'] == 'University Uppsala'
    assert zenodo['description'] == '<p>, C &amp; Hammarstr&ouml;m, Harald &amp; Forkel, Robert. '\
                                    '1999. Glottolog 3.3. ' \
                                    'Jena: Max Planck Institute for the Science of Human History. '\
                                    '(Available online at ' \
                                    '<a href="https://glottolog.org">https://glottolog.org</a>)</p>'
