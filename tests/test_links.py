from pyglottolog.links import endangeredlanguages


def test_el(mocker):
    class EL(object):
        def get(self, *args, **kw):
            return mocker.Mock(text='1,abc,Name,,,,,,,,,,"10,20.02 ;"')

    mocker.patch('pyglottolog.links.endangeredlanguages.requests', EL())
    res = endangeredlanguages.read()
    assert len(res) == 1
    assert len(res[0].coordinates) == 1
    assert res[0].url.endswith('1')
