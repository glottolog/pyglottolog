from pyglottolog.links import endangeredlanguages


def test_el(api_copy, mocker, capsys):
    class EL(object):
        def get(self, url, *args, **kw):
            content = ''
            if '/region' in url:
                content = '<a href="/lang/country/">C</a>'
            elif '/country' in url:
                content = '<a href="/lang/123">L</a>'
            elif '123' in url:
                content = ''
            return mocker.Mock(content='<html>{0}</html>'.format(content))

    mocker.patch('pyglottolog.links.endangeredlanguages.requests', EL())
    endangeredlanguages.scrape(api_copy)
    out, _ = capsys.readouterr()
    assert 'fetch' in out
