import pytest

from pyglottolog.links import wikidata


def test_wikidata(mocker, api_copy):
    langs = {l.id: l for l in api_copy.languoids()}
    with pytest.raises(AssertionError):
        _ = list(wikidata.Wikidata().iterupdated(langs.values()))
