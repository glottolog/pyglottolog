import pathlib

import pytest

from pyglottolog.references import Entry


def test_BibFiles_getitem(bibfiles):
    bf = bibfiles[0]
    assert len(list(bf.iterentries())) == 3 and bf.size and bf.mtime


def test_BibFiles_roundtrip(capsys, bibfiles_copy):
    bibfiles_copy.roundtrip_all()
    assert 'a.bib' in capsys.readouterr()[0]


def test_BibFile(tmpdir, bibfiles):
    bf = bibfiles['a.bib']
    assert bf['a:key'].type == 'misc'
    assert bf['s:Andalusi:Turk'].key == 's:Andalusi:Turk'

    for entry in bf.iterentries():
        if entry.key == 'key':
            assert len(list(entry.languoids({'abc': 1})[0])) == 1

    with pytest.raises(KeyError):
        bf['xyz']

    assert len(list(bf.iterentries())) == 3

    lines = [line for line in pathlib.Path(bf.fname).read_text(encoding='utf8').split('\n')
             if not line.strip().startswith('glottolog_ref_id')]
    (tmpdir / 'a.bib').write_text('\n'.join(lines), encoding='utf8')

    entries = bf.load()  # FIXME
    bf.fname = str(tmpdir / ' newa.bib')
    bf.save(entries)

    bf.update(str(tmpdir / 'a.bib'))
    assert len(list(bf.iterentries())) == 3

    bf.update(bibfiles['b.bib'].fname)
    assert len(list(bf.iterentries())) == 1

    def visitor(entry):
        entry.fields['new_field'] = 'a'

    bf.visit(visitor=visitor)
    for entry in bf.iterentries():
        assert 'new_field' in entry.fields

    bf.visit(visitor=lambda e: True)
    assert len(bf.keys()) == 0


def test_BibFile_show_characters(capsys, bibfiles):
    bibfiles['b.bib'].show_characters()
    assert 'CJK UNIFIED IDEOGRAPH' in capsys.readouterr()[0]


def test_Entry_lgcodes():
    assert Entry.lgcodes(None) == []


@pytest.mark.parametrize(
    'publisher,address,p_and_a',
    [
        ('Berlin: LSP', None, ('LSP', 'Berlin')),
        ('LSP', 'Berlin', ('LSP', 'Berlin')),
        ('Kassel: LSP', 'Berlin', ('Kassel: LSP', 'Berlin')),
    ]
)
def test_Entry_publisher_and_address(publisher, address, p_and_a):
    e = Entry('x', 'misc', dict(publisher=publisher, address=address), None)
    assert e.publisher_and_address == p_and_a


@pytest.mark.parametrize(
    'smaller,bigger',
    [
        # Better doctype wins:
        (dict(hhtype='grammar_sketch'), dict(hhtype='grammar')),
        # More pages wins:
        (dict(hhtype='grammar', pages='120'), dict(hhtype='grammar', pages='340')),
        # More recent year wins:
        (dict(hhtype='grammar', year='1900'), dict(hhtype='grammar', year='2000')),
        (dict(hhtype='grammar', year='2000'), dict(hhtype='grammar', year='1800[2010]')),
        # Page number is divided by number of described languages:
        (
            dict(hhtype='grammar', pages='200', lgcode='[abc],[cde],[efg]'),
            dict(hhtype='grammar', pages='100')),
    ]
)
def test_Entry_weight(smaller, bigger, mocker):
    a = Entry('x', 'misc', smaller, mocker.Mock())
    b = Entry('x', 'misc', bigger, mocker.Mock())
    assert a < b
    assert a != b


def test_Entry_weight_with_api(api, mocker):
    assert Entry('x', 'misc', dict(hhtype='grammar'), mocker.Mock(), api) > \
           Entry('x', 'misc', dict(hhtype='other'), mocker.Mock(), api)


@pytest.mark.parametrize(
    'fields,expected',
    [
        (dict(hhtype='grammar', pages='400'), 'long_grammar'),
        (dict(hhtype='grammar'), 'grammar'),
        (dict(hhtype='grammar_sketch'), 'grammar_sketch'),
        (dict(hhtype='phonology'), 'phonology_or_text'),
        (dict(hhtype='wordlist'), 'wordlist_or_less'),
        (dict(hhtype='xyz'), 'wordlist_or_less'),
    ]
)
def test_Entry_med(fields, expected, mocker, api):
    e = Entry('x', 'misc', fields, mocker.Mock(), api=api)
    assert e.med_type == api.med_types.get(expected)


@pytest.mark.parametrize(
    'fields,expected',
    [
        (dict(numberofpages='123'), 123),
        (dict(numberofpages='x123'), None),
        (dict(pages='xvii'), 17),
        (dict(pages='x+23'), 33),
        (dict(pages='125-9pp.'), 5),
        (dict(pages='125-100'), 26),
        (dict(pages='123456'), None),
        (dict(pages='x+123456'), None),
        (dict(pages='123456-423457'), None),
    ]
)
def test_Entry_pages_int(fields, expected):
    e = Entry('x', 'misc', fields, None)
    assert e.pages_int == expected


@pytest.fixture
def entry():
    return Entry('x', 'misc', {'hhtype': 'grammar (computerized assignment from "xyz")'}, None)


def test_Entry(entry):
    assert entry.doctypes({'grammar': 1}) == ([1], 'xyz')
