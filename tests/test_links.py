from pyglottolog.links import endangeredlanguages


def test_el(elcat):
    res = endangeredlanguages.read()
    assert len(res) == 1
    assert len(res[0].coordinates) == 1
    assert res[0].url.endswith('1')
