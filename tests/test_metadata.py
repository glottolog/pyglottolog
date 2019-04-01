from clldutils.jsonlib import load

from pyglottolog.metadata import prepare_release


def test_read_editors(api_copy):
    prepare_release(api_copy, '3.3')
    zenodo = load(api_copy.path('.zenodo.json'))
    assert zenodo['creators'][1]['affiliation'] == 'University Uppsala'
