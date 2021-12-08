import pytest

from pyglottolog.links import endangeredlanguages, wikidata


def test_el(elcat):
    res = endangeredlanguages.read()
    assert len(res) == 1
    assert len(res[0].coordinates) == 1
    assert res[0].url.endswith('1')


def test_el_altnames():
    lang = endangeredlanguages.ElCatLanguage(
        id=1,
        isos='',
        name=' инари-саамский язык',
        also_known_as='инари-саамский язык; Anárašgiella; Enaresamiska; "Inari Lappish;"',
        status=None,
        speakers=None,
        classification=None,
        variants_and_dialects='',
        u=None,
        comment=None,
        countries='',
        continent=None,
        coordinates='1;2',
    )
    assert '"Inari Lappish"' in lang.also_known_as
    assert '"' not in lang.also_known_as
    assert len(lang.also_known_as) == 4


def test_wikidata(mocker, api_copy):
    langs = {l.id: l for l in api_copy.languoids()}
    with pytest.raises(AssertionError):
        _ = list(wikidata.Wikidata().iterupdated(langs.values()))
