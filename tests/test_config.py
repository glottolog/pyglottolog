from pyglottolog.config import Config, AES, DocumentType, Macroarea


def test_aes(api_copy):
    aes = Config.from_ini(api_copy.repos / 'config' / 'aes_status.ini', AES)
    assert aes.safe < aes.definite
    assert aes.vulnerable == aes.get('threatened')


def test_macroarea(api_copy):
    ma = Config.from_ini(api_copy.repos / 'config' / 'macroareas.ini', Macroarea)
    assert ma.__defaults__['description']
    assert ma.eurasia.geojson is None


def test_doctype(api_copy):
    dt = Config.from_ini(api_copy.repos / 'config' / 'document_types.ini', DocumentType)
    assert dt.grammar > dt.grammar_sketch


def test_editors(api_copy):
    assert len([e for e in api_copy.editors.values() if not e.current]) == 2
    assert len([e for e in api_copy.editors.values() if e.current]) == 3
