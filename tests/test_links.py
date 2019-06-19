from pyglottolog.links import endangeredlanguages, wikidata


def test_el(elcat):
    res = endangeredlanguages.read()
    assert len(res) == 1
    assert len(res[0].coordinates) == 1
    assert res[0].url.endswith('1')


def test_wikidata(mocker, api_copy):
    class wd(object):
        def post(self, *args, **kw):
            return mocker.Mock(text='glottocode,item,wikipedia\nabcd1235,http://example.org,xyz')

    langs = {l.id: l for l in api_copy.languoids()}
    mocker.patch('pyglottolog.links.wikidata.requests', wd())
    assert list(wikidata.Wikidata().iterupdated(langs.values()))
    assert 'http://example.org' in [l.url for l in langs['abcd1235'].links]
    assert not list(wikidata.Wikidata().iterupdated(langs.values()))
