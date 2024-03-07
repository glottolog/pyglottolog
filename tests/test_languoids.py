import pathlib

import pytest


from pyglottolog.languoids import (Languoid,
    Glottocodes, Glottocode, Country, Reference,
    ClassificationComment, EthnologueComment, Link)


def test_legacy_imports():
    from pyglottolog import objects
    assert objects.Glottocode is Glottocode
    assert objects.Reference is Reference


def test_Link():
    assert Link.from_(dict(url='xyz')).label is None
    assert Link.from_('[label](url)').url == 'url'
    assert 'url' in Link.from_('[label](url)').__json__()
    assert Link.from_string('abc').to_string() == 'abc'

    with pytest.raises(TypeError):
        Link.from_(5)


def test_Glottocodes(tmpdir):
    json = tmpdir / 'glottocodes.json'
    json.write_text('{}', encoding='ascii')

    glottocodes = Glottocodes(str(json))
    gc = glottocodes.new('a', dry_run=True)
    assert gc.startswith('aaaa')
    assert gc not in glottocodes
    gc = glottocodes.new('a')
    assert gc in glottocodes
    # make sure it's also written to file:
    assert gc in Glottocodes(str(json))
    assert len(list(Glottocodes(str(json)))) == 1


@pytest.mark.parametrize('input_, valid', [
    ('abcd1234', True),
    ('a12d3456', True),
    ('abcd123', False),
    ('12d3456', False),
    ('aNOCODE', False),
    ('NOCODE_abd', False),
    ('nocode', False),
])
def test_pattern(input_, valid, _match=Glottocode.pattern.match):
    assert (_match(input_) is not None) == valid


@pytest.mark.parametrize('text, expected_id, expected_str', [
    ('Germany', 'DE', 'DE'),
    ('Russian Federation (RU)', 'RU', 'RU'),
    ('RU', 'RU', 'RU'),
])
def test_Country_from_text(text, expected_id, expected_str):
    country = Country.from_text(text)
    assert country.id == expected_id
    assert str(country) == expected_str


def test_Country_from_name():
    assert Country.from_name('abcdefg') is None


def test_Country_from_id():
    assert Country.from_id('abcdefg') is None


def test_Glottocode_validation():
    with pytest.raises(ValueError):
        Glottocode('a2')


def test_Glottocode_ordering():
    assert sorted([Glottocode('abcd1235'), Glottocode('abcd1234')])[0] == Glottocode('abcd1234')
    assert Glottocode('zzzz9999') > Glottocode('abcd1234')
    assert Glottocode('abcd1234') <= Glottocode('abcd1234')


def test_Reference():
    ref = Reference('bib:key', '12-34', 'German')
    assert '{0}'.format(ref) == '**bib:key**:12-34<trigger "German">'
    Reference.from_list(['{0}'.format(ref)])

    with pytest.raises(ValueError):
        Reference.from_list(['abc'])

    match = Reference.pattern.match('**bib:k(e)y(**)')
    assert match.group('key') == 'bib:k(e)y'
    assert match.group('endtag') == '(**)'


def test_ClassificationComment(mocker):
    cc = ClassificationComment(family='**bib:key**')
    log = mocker.Mock()
    cc.check(mocker.Mock(), [], log)
    assert log.error.called
    log = mocker.Mock()
    cc.check(mocker.Mock(), ['bib:key'], log)
    assert not log.error.called
    cc = ClassificationComment(sub='A comment about **bib:key**:10-12', subrefs=['**bib:key**:20'])
    refs = cc.merged_refs('sub')
    assert len(refs) == 1
    assert refs[0].pages == '10-12;20'


def test_EthnologueComment(mocker):
    with pytest.raises(ValueError):
        EthnologueComment('abc', 't')

    with pytest.raises(ValueError):
        EthnologueComment('abc', 'missing', 'E15')

    with pytest.raises(ValueError):
        EthnologueComment('abc', 'missing', 'E16')

    with pytest.raises(ValueError):
        EthnologueComment('abc', 'missing', 'E16', '\u00e4\u00f6\u00fc'.encode('utf-8'))

    log = mocker.Mock()
    ec = EthnologueComment('abc', 'missing', 'E16', 'abc')
    ec.check(mocker.Mock(), [], log)
    assert not log.error.called

    log = mocker.Mock()
    ec = EthnologueComment('abc', 'missing', 'E16', '**bib:key**')
    ec.check(mocker.Mock(), [], log)
    assert log.error.called


def test_ancestors(api):
    lang = api.languoid('dial1234')
    assert 'isol1234' in ','.join(repr(a) for a in lang.ancestors)


def test_endangerment(api):
    lang = api.languoid('abcd1235')
    assert lang.endangerment.status == api.aes_status.sleeping
    assert 'source' in lang.endangerment.__json__()


def test_timespan(api, tmpdir, recwarn):
    assert api.languoid('abcd1235').timespan == None

    with pytest.raises(ValueError):
        api.languoid('abcd1235').timespan = (1,)

    l = api.languoid('abcd1235')
    l.timespan = (-1, 300)
    assert l.timespan == (-1, 300)

    p = pathlib.Path(str(tmpdir))
    l.write_info(p)
    assert '-0001-01-01/0300-01-01' in p.joinpath('abcd1235', 'md.ini').read_text(encoding='utf8')

    l.timespan = (-10000, 2000)
    assert recwarn.pop(UserWarning)


def test_Level(api):
    assert api.languoid_levels.dialect > api.languoid_levels.language
    assert api.languoid_levels.language == api.languoid('abcd1235').level
    with pytest.raises(ValueError):
        api.languoid_levels.get('abcde')


def test_Category(api):
    assert api.languoid('book1243').category == api.language_types.bookkeeping.category
    assert api.languoid('abcd1235').category == api.language_types.spoken_l1.category
    assert api.languoid('dial1234').category == 'Dialect'


def test_sources(api):
    assert api.languoid('book1242').sources == []
    with pytest.raises(AssertionError):
        api.languoid('book1242').sources = [1]
    api.languoid('book1242').sources = [Reference('key')]


def test_ethnologue_comment(api):
    assert api.languoid('book1243').ethnologue_comment.comment_type == 'missing'
    assert api.languoid('book1243').ethnologue_comment.__json__()


def test_classification_comment(api):
    assert api.languoid('abcd1234').classification_comment


def test_coordinates_setter(api, tmpdir):
    l = api.languoid('abcd1234')
    l.latitude = 1.12345678
    l.longitude = 1.123456789
    l.write_info(pathlib.Path(str(tmpdir)))
    ini = pathlib.Path(str(tmpdir)).joinpath('abcd1234', 'md.ini').read_text(encoding='utf8')
    assert 'latitude = 1.12346' in ini and 'longitude = 1.12346'


def test_classification_setter(api, tmpdir):
    l = api.languoid('abcd1234')
    l.cfg.set('classification', 'familyrefs', ['abc', 'def'])
    l.write_info(pathlib.Path(str(tmpdir)))
    ini = pathlib.Path(str(tmpdir)).joinpath('abcd1234', 'md.ini').read_text(encoding='utf8')
    assert '\tabc\n\tdef' in ini


def test_Languoid_sorting(api):
    assert api.languoid('abcd1235') < api.languoid('abcd1236')
    assert api.languoid('abcd1236') >= api.languoid('abcd1235')


def test_factory_without_api(api_copy):
    f = Languoid.from_dir(api_copy.tree / 'abcd1234', _api=api_copy)
    l = Languoid.from_dir(api_copy.tree / f.id / 'abcd1235')
    assert len(l.macroareas) == 0  # No API passed at initialization => no macroareas!


def test_factory(tmpdir, api_copy):
    f = Languoid.from_dir(api_copy.tree / 'abcd1234', _api=api_copy)
    assert f.category == 'Family'
    l = Languoid.from_dir(api_copy.tree / f.id / 'abcd1235', _api=api_copy)
    assert l.name == 'language'
    assert 'abcd1235' in repr(l)
    assert 'language' in '%s' % l
    assert l.level == api_copy.languoid_levels.language
    assert l.latitude == pytest.approx(0.5)
    assert l.longitude == pytest.approx(-30)
    l.latitude, l.longitude = 1.0, 1.0
    assert l.latitude == pytest.approx(1.0)
    assert l.longitude == pytest.approx(1.0)
    assert l.iso_code == 'abc'
    l.iso_code = 'cde'
    assert l.iso == 'cde'
    assert l.hid == 'abc'
    l.hid = 'abo'
    assert l.hid == 'abo'
    assert l.id == 'abcd1235'

    assert len(l.macroareas) == 2
    l.macroareas = [api_copy.macroareas.pacific]
    assert l.macroareas == [api_copy.macroareas.get('Papunesia')]

    l.countries = api_copy.countries[:2]
    assert len(l.countries) == 2

    assert l.parent == f
    assert l in f.children
    assert l.children[0].family == f
    l.write_info(str(tmpdir))
    assert (tmpdir / 'abcd1235').exists()
    assert isinstance(api_copy.languoid('abcd1235').iso_retirement.asdict(), dict)
    assert l.classification_comment is None
    assert l.names == {}
    l.cfg['altnames'] = {'glottolog': 'xyz'}
    assert 'glottolog' in l.names
    assert l.identifier == {}
    l.cfg['identifier'] = {'multitree': 'xyz'}
    assert 'multitree' in l.identifier


def test_isolate(api):
    l = Languoid.from_dir(api.tree / 'isol1234')
    assert l.isolate
    assert l.parent is None
    assert l.family is None


def test_closest_iso(api):
    assert api.languoid('abcd1235').closest_iso() == 'abc'
    assert api.languoid('abcd1236').closest_iso() == 'abc'


def test_attrs(api):
    l = Languoid.from_name_id_level(api.tree, 'name', 'abcd1235', 'language', hid='NOCODE')
    l.name = 'other'
    assert l.name == 'other'
    with pytest.raises(AttributeError):
        l.glottocode = 'x'
    with pytest.raises(AttributeError):
        l.id = 'x'
    assert l.id == l.glottocode
    assert l.hid == 'NOCODE'


def test_iter_descendants(api):
    children = [l.id for l in api.languoid('abcd1234').iter_descendants()]
    assert set(children) == {'abcd1235', 'abcd1236', 'abcd1237'}
    