import shlex
import shutil
import logging

import pytest

from pyglottolog.__main__ import admin_main


@pytest.fixture
def _main(api_copy, mocker):
    def f(*args, **kw):
        kw.setdefault('log', mocker.Mock())
        if len(args) == 1 and isinstance(args[0], str):
            args = shlex.split(args[0])
        admin_main(args=['--repos', str(api_copy.repos)] + list(args), **kw)
    return f


def test_release(_main):
    with pytest.raises(AssertionError):
        _main('release --version 1.0.1.dev0')
    _main('release --version 2.7')


def test_update_links(_main, capsys):
    _main('updatelinks none')
    out, _ = capsys.readouterr()
    assert '0 languoids updated' in out


def test_lff(capsys, _main, api_copy, encoding='utf-8'):
    _main('tree2lff')

    dff = api_copy.build_path('dff.txt')
    dfftxt = dff.read_text(encoding=encoding).replace('dialect', 'Dialect Name')
    dff.write_text(dfftxt, encoding=encoding)
    _main('lff2tree')
    assert 'git status' in capsys.readouterr()[0]
    assert api_copy.languoid('abcd1236').name == 'Dialect Name'
    # Old language and dialect names are retained as alternative names:
    assert 'dialect' in api_copy.languoid('abcd1236').names['glottolog']

    _main('tree2lff')
    _ = dff.read_text(encoding=encoding)


def test_index(api_copy, _main):
    _main('langindex')
    assert len(list(api_copy.repos.joinpath('languoids').glob('*.md'))) == 10


def test_update_macroareas(_main, capsys):
    _main('updatemacroareas')
    out, _ = capsys.readouterr()
    assert '1 dialects updated' in out


def test_update_sources(_main, capsys):
    _main('updatesources')
    out, _ = capsys.readouterr()
    assert '2 languoids updated' in out


def test_check(capsys, _main, mocker, api_copy):
    _main('check --bib-only')

    log = mocker.Mock()
    _main('check --tree-only', log=log)
    assert 'family' in capsys.readouterr()[0]
    msgs = [a[0] for a, _ in log.error.call_args_list]
    assert any('unregistered glottocode' in m for m in msgs)
    assert any('missing reference' in m for m in msgs)
    assert len(msgs) == 28

    shutil.copytree(
        api_copy.tree / 'abcd1234' / 'abcd1235',
        api_copy.tree / 'abcd1235')

    log = mocker.Mock()
    _main('check --tree-only', log=log)
    msgs = [a[0] for a, _ in log.error.call_args_list]
    assert any('duplicate glottocode' in m for m in msgs)
    assert len(msgs) == 30

    (api_copy.tree / 'abcd1235').rename(api_copy.tree / 'abcd1238')
    log = mocker.Mock()
    _main('check --tree-only', log=log)
    msgs = [a[0] for a, _ in log.error.call_args_list]
    assert any('duplicate hid' in m for m in msgs)
    assert len(msgs) >= 9


def test_check_2(_main, mocker, caplog):
    mocker.patch('pyglottolog.iso.check_lang', lambda _, i, l, **kw: ('warn', l, 'xyz'))
    _main('check --tree-only', log=logging.getLogger(__name__))
    for record in caplog.records:
        print(record.message)


def test_monster(capsys, _main):
    _main('bib')
    assert capsys.readouterr()[0]
