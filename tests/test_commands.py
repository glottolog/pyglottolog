import shlex
import logging

import pytest

from pyglottolog.__main__ import main


@pytest.fixture
def _main(api_copy, mocker):
    def f(*args, **kw):
        kw.setdefault('log', mocker.Mock())
        kw['test'] = True
        if len(args) == 1 and isinstance(args[0], str):
            # Windows: shlex.split() drops backslashes, e.g. in paths
            #          shlex.split(posix=False) does not parse quotes
            #          However: supprocess.Popen does not use it
            #          Workaround: use pathlib.Path.as_posix()
            # https://stackoverflow.com/questions/33560364/python-windows-parsing-command-lines-with-shlex
            args = shlex.split(args[0])
        main(args=['--repos', str(api_copy.repos)] + list(args), **kw)
    return f


def test_help(_main, capsys):
    _main()
    out, _ = capsys.readouterr()
    assert 'usage' in out


def test_no_repos(tmpdir):
    with pytest.raises(SystemExit):
        main(args=['--repos', str(tmpdir.join('x')), 'show', 'abcd1235'])


def test_show(capsys, _main):
    _main('show **a:key**')
    assert '@misc' in capsys.readouterr()[0]

    _main('show a:key')
    assert '@misc' in capsys.readouterr()[0]

    _main('show abcd1236')
    assert 'Classificat' in capsys.readouterr()[0]


def test_edit(mocker, _main):
    mocker.patch('pyglottolog.commands.edit.subprocess')
    _main('edit abcd1236')


def test_create(capsys, _main, api_copy):
    with pytest.raises(SystemExit):
        _main('create abcd1249 "new name" language')

    _main('create abcd1234 "new name" language')
    assert 'Info written' in capsys.readouterr()[0]
    assert 'new name' in [c.name for c in api_copy.languoid('abcd1234').children]

    with pytest.raises(SystemExit):
        _main('create {0} "new name" language'.format(
            (api_copy.repos / 'languoids' / 'tree' / 'abcd1249').as_posix()))

    _main('create {0} "new name" language'.format(
        (api_copy.repos / 'languoids' / 'tree' / 'abcd1234').as_posix()))


def test_fts(capsys, _main):
    with pytest.raises(SystemExit):
        _main('refsearch "Harzani year:1334"')

    _main('searchindex')
    _main('refsearch "Harzani year:1334"')
    assert "'Abd-al-'Ali Karang" in capsys.readouterr()[0]

    _main('langsearch id:abcd*')
    assert "abcd1234" in capsys.readouterr()[0]

    _main('langsearch classification')
    assert "abcd1234" in capsys.readouterr()[0]


def test_metadata(capsys, _main):
    _main('langdatastats')
    assert "longitude" in capsys.readouterr()[0]


def test_tree(capsys, _main):
    with pytest.raises(SystemExit):
        _main('tree')

    with pytest.raises(SystemExit):
        _main('tree xyz')

    _main('tree abc --maxlevel language')
    out, _ = capsys.readouterr()
    assert 'language' in out
    assert 'dialect' not in out

    _main('tree abcd1234 --newick --maxlevel 1')
    _main('tree abcd1235 --newick --maxlevel 5')
    assert 'language' in capsys.readouterr()[0]
    _main('tree abcd1234 --newick --maxlevel language')
    out, _ = capsys.readouterr()
    assert out.splitlines()[-1] == \
           "('language [abcd1235][abc]-l-':1," \
           "'language2 [abcd1237]-l-':1)'family [abcd1234][aaa]':1;"


def test_languoids(capsys, _main, tmp_path):
    _main('languoids --output={0}'.format(tmp_path.as_posix()))
    out, _ = capsys.readouterr()
    assert '-metadata.json' in out
    assert tmp_path.glob('*.csv')


def test_htmlmap(_main, tmp_path):
    _main('htmlmap --output {0} --min-langs-for-legend 1'.format(tmp_path.as_posix()))
    assert tmp_path.joinpath('glottolog_map.html').exists()
    tmp_path.joinpath('glottocodes').write_text('abcd1234\nabcd1235,5,8\n', encoding='utf8')
    _main('htmlmap --output {0} --glottocodes {1}'.format(tmp_path.as_posix(),
                                                          (tmp_path / 'glottocodes').as_posix()))

    with pytest.raises(SystemExit):
        _main('htmlmap --output {0}'.format((tmp_path /'xyz').as_posix()))

    with pytest.raises(SystemExit):
        _main('htmlmap --glottocodes {0}'.format(tmp_path.joinpath('xyz')))


def test_iso2codes(_main, tmp_path):
    _main('iso2codes --output {0}'.format(tmp_path.as_posix()))
    assert tmp_path.joinpath('iso2glottocodes.csv').exists()

