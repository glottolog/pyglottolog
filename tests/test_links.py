from pyglottolog.links import endangeredlanguages


def test_el(mocker):
    class EL(object):
        def get(self, url, *args, **kw):
            return mocker.Mock(text="1,abc,Name,,,,,,,,,,")

    mocker.patch('pyglottolog.links.endangeredlanguages.requests', EL())
    assert len(endangeredlanguages.read()) == 1
