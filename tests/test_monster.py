from pyglottolog import monster


def test_main(capsys, api_copy):
    monster.compile(api_copy)
    out, _ = capsys.readouterr()
    assert len(out.splitlines()) == 50
    assert '2 splitted' in out
    assert '2 merged' in out
