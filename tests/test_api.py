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
    assert len(l.descendants_from_nodemap(nodemap)) == 2
    assert len(l.descendants_from_nodemap(nodemap, level=api.languoid_levels.language)) == 1
    assert len(l.descendants_from_nodemap(nodemap, level='dialect')) == 1

    with pytest.raises(ValueError):
        l.descendants_from_nodemap(nodemap, level='dialects')


def test_languoids(api):
    assert len(list(api.languoids())) == 7
    assert len(list(api.languoids(maxlevel=api.languoid_levels.family))) == 2
    assert len(list(api.languoids(maxlevel=0))) == 3
    assert len(list(api.languoids(maxlevel=0, exclude_pseudo_families=True))) == 2
    assert len(list(api.languoids(maxlevel=api.languoid_levels.language))) == 5
    assert len(api.languoids_by_code()) == 10
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
        "(('dialect [abcd1236]':1)'language [abcd1235][abc]-l-':1)'family [abcd1234][aaa]':1;"
    }


def test_hhtypes(api):
    assert len(api.hhtypes) == 16


def test_load_triggers(api):
    assert len(api.triggers) == 2


def test_macroarea_map(api):
    assert api.macroarea_map['abc'] == 'Eurasia'
