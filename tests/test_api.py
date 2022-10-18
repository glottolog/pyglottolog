import pytest


def test_legacy_import():
    from pyglottolog import api
    from pyglottolog import Glottolog
    assert api.Glottolog is Glottolog


def test_glottolog_invalid_repos(tmpdir):
    from pyglottolog import Glottolog
    with pytest.raises(ValueError, match=r'missing tree dir'):
        Glottolog(str(tmpdir))

    tmpdir.join('languoids').mkdir()
    tmpdir.join('languoids', 'tree').mkdir()

    with pytest.raises(ValueError, match=r'missing references subdir'):
        Glottolog(str(tmpdir))


def test_cache(caching_api, api):
    lang = api.languoid('abcd1234')
    assert lang is not api.languoid('abcd1234')

    lang = caching_api.languoid('abcd1234')
    assert lang is caching_api.languoid('abcd1234')
    assert caching_api.languoid('aaa') is lang
    l2 = caching_api.languoid('abc')
    assert l2.id == 'abcd1235'
    assert l2.ancestors


def test_cache_languoids(caching_api):
    assert 'aaa' not in caching_api.cache
    assert 'abcd1234' not in caching_api.cache
    _ = list(caching_api.languoids())
    assert 'aaa' in caching_api.cache
    assert 'abcd1234' in caching_api.cache


def test_refs_by_languoid(api):
    res = api.refs_by_languoid()
    assert len(res[0]) == 2
    assert len(res[1]) == 7
    res = api.refs_by_languoid('a')
    assert len(res[0]) == 1


def test_editors(api):
    eids = [
        e.id for e in sorted(api.editors.values(), key=lambda i: int(i.ord))
        if e.current]
    assert eids[0] == 'hammarstroem'


def test_paths(api):
    assert api.ftsindex


def test_languoid(api):
    assert api.languoid('abc').name == 'language'


def test_descendants_from_nodemap(api):
    nodemap = {n.id: n for n in api.languoids()}
    l = api.languoid('abcd1234')
    assert len(l.descendants_from_nodemap(nodemap)) == 3
    assert len(l.descendants_from_nodemap(nodemap, level=api.languoid_levels.language)) == 2
    assert len(l.descendants_from_nodemap(nodemap, level='dialect')) == 1

    with pytest.raises(ValueError):
        l.descendants_from_nodemap(nodemap, level='dialects')


def test_languoids(api):
    assert len(list(api.languoids())) == 8
    assert len(list(api.languoids(maxlevel=api.languoid_levels.family))) == 2
    assert len(list(api.languoids(maxlevel=0))) == 3
    assert len(list(api.languoids(maxlevel=0, exclude_pseudo_families=True))) == 2
    assert len(list(api.languoids(maxlevel=api.languoid_levels.language))) == 6
    assert len(api.languoids_by_code()) == 11
    assert api.languoids_by_code(nodes={}) == {}
    assert 'NOCODE_Family-name' in api.languoids_by_code()


def test_newick_tree(api):
    assert api.newick_tree(start='abcd1235') == \
        "('dialect [abcd1236]':1)'language [abcd1235][abc]-l-':1;"
    assert api.newick_tree(start='abcd1235') == \
        api.newick_tree(start='abcd1235', nodes={l.id: l for l in api.languoids()})
    assert api.newick_tree(start='abcd1235', template='{l.id}') == "(abcd1236:1)abcd1235:1;"
    assert set(api.newick_tree().split('\n')) == {
        "(('isolate {dialect} [dial1234]':1)'isolate [isol1234]-l-':1)'isolate [isol1234]':1;",
        "(('dialect [abcd1236]':1)'language [abcd1235][abc]-l-':1,"
        "'language2 [abcd1237]-l-':1)'family [abcd1234][aaa]':1;"
    }


def test_hhtypes(api):
    assert len(api.hhtypes) == 16


def test_load_triggers(api):
    assert len(api.triggers) == 2


def test_macroarea_map(api):
    assert api.macroarea_map['abc'] == 'Eurasia'
