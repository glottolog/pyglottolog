from pyglottolog.config import Config, AES, DocumentType


def test_aes(api_copy):
    aes = Config.from_ini(api_copy.repos / 'config' / 'aes_status.ini', AES)
    assert aes.safe < aes.definite
    assert aes.vulnerable == aes.get('threatened')


def test_doctype(api_copy):
    dt = Config.from_ini(api_copy.repos / 'config' / 'document_types.ini', DocumentType)
    assert dt.grammar > dt.grammar_sketch
