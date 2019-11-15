import operator

import pytest

from pyglottolog.references.libmonster import (markconservative, markall,
    add_inlg_e, INLG, keyid, pyear, pagecount, lgcode, grp2fd, bibord_iteritems)


def test_bibord_iteritems():
    def d(l):
        return {k: 1 for k in l}
    assert [r[0] for r in bibord_iteritems(d(['zcustom', 'editor', 'custom', 'author']))] == \
           ['author', 'editor', 'custom', 'zcustom']


@pytest.mark.parametrize(
    'current,previous,assertion',
    [
        (
            {'title': 'Grammar'},
            {'title': 'Grammar'},
            lambda f: operator.eq(f['hhtype'].split()[0], 'grammar')),
        (  # If a higher hhtype is computed, this cancels out previous computations.
            {'title': 'grammar', 'lgcode': 'abc'},
            {'title': 'other', 'hhtype': 'wordlist', 'lgcode': 'abc'},
            lambda f: not operator.contains(f, 'hhtype')),
        (
            {'title': 'Grammar'},
            {'title': 'Grammar', 'hhtype': 'grammar'},
            lambda f: operator.eq(f['hhtype'].split()[0], 'grammar')),
        (
            {'title': 'other', 'hhtype': 'grammar'},
            {'title': 'Grammar of lang'},
            lambda f: operator.eq(f['hhtype'].split()[0], 'grammar')),
    ]
)
def test_markconcservative(tmpdir, hhtypes, current, previous, assertion):
    res = markconservative(
        {1: ('article', current), 2: ('article', {'lgcode': 'abc'})},
        hhtypes.triggers,
        {1: ('article', previous)},
        hhtypes,
        str(tmpdir / 'marks.txt'),
        verbose=False)
    assert assertion(res[1][1])


def test_markconservative_2(tmpdir, hhtypes):
    res = markconservative(
        {}, hhtypes.triggers, {}, hhtypes, str(tmpdir / 'marks.txt'), verbose=False)
    assert not res


@pytest.mark.parametrize(
    'fields,expected',
    [
        ({'title': "other grammar of lang"}, 'grammar'),
        ({'title': "grammar and phonologie and morphologie"}, 'morphologie and phonologie;grammar'),
        ({'title': "fonologia and phonemic", 'hhtype': "grammar"}, 'grammar'),
        ({'title': "grammar and fonologia and phonemic"}, 'grammar'),
    ]
)
def test_markall_hhtype(hhtypes, fields, expected):
    bib = {1: ('article', fields)}
    markall(bib, hhtypes.triggers, verbose=False, rank=lambda l: hhtypes[l].rank)
    assert expected in bib[1][1]['hhtype']


def test_markall_lgcode(api):
    bib = {1: ('article', {'title': "other grammar of lang"})}
    markall(bib, api.triggers['lgcode'], verbose=False)
    assert 'language' in bib[1][1]['lgcode']


def test_add_inlg_e(api):
    res = add_inlg_e(
        {1: ('article', {'title': 'Grammar of language'})},
        api.triggers[INLG],
        verbose=False)
    assert res[1][1][INLG] == 'language [abc]'


@pytest.mark.parametrize('fields, expected', [
    ({}, '__missingcontrib__'),
    ({'author': 'An Author'}, 'author_no-titlend'),
    ({'editor': 'An Author'}, 'author_no-titlend'),
    ({'author': 'An Author', 'title': 'A rather long title'}, 'author_rather-longnd'),
    ({'author': 'An Author', 'title': 'Title', 'year': '2014'}, 'author_title2014'),
    ({'author': 'An Author', 'volume': 'IV'}, 'author_no-titleivnd'),
    ({'author': 'An Author', 'extra_hash': 'a'}, 'author_no-titlenda'),
])
def test_keyid(fields, expected):
    assert keyid(fields, {}) == expected


def test_keyid_invalid(capsys):
    assert keyid({'author': 'An Author and '}, {}) == 'author_no-titlend'
    assert 'Unparsed' in capsys.readouterr()[0]


@pytest.mark.parametrize('year, expected', [
    ('', '[nd]'),
    ('1931', '1931'),
    ('1931-32', '1931-1932'),
])
def test_pyear(year, expected):
    assert pyear(year) == expected


@pytest.mark.parametrize('pages, expected', [
    ('', ''),
    ('1', '1'),
    ('10-20', '11'),
    ('10-20,v-viii', '4+11'),
    ('20,viii', '8+20'),
    ('10-2', '3'),  # interpreted as 10-12
])
def test_pagecount(pages, expected):
    assert pagecount(pages) == expected


@pytest.mark.parametrize('lgcode_, expected', [
    ('', []),
    ('[abc]', ['abc']),
    ('abc,NOCODE_Abc', ['abc', 'NOCODE_Abc']),
])
def test_lgcode(lgcode_, expected):
    assert lgcode((None, {'lgcode': lgcode_})) == expected


@pytest.mark.parametrize('input_, expected', [
    ([(1, 2), (1, 3), (2, 4), (1, 5)], {1: {2: 1, 3: 1, 5: 1}, 2: {4: 1}}),
])
def test_grp2fd(input_, expected):
    assert grp2fd(input_) == expected
