import shutil
import pathlib

import pytest

import pyglottolog

TESTS_DIR = pathlib.Path(__file__).parent


@pytest.fixture
def elcat(mocker):
    class EL(object):
        def get(self, *args, **kw):
            return mocker.Mock(text='1,abc,Name,,,,,,,,,,"10,20.02 ;"')

    mocker.patch('pyglottolog.links.endangeredlanguages.requests', EL())


@pytest.fixture(scope='session')
def repos_path():
    return TESTS_DIR / 'repos'


@pytest.fixture(scope='session')
def references_path(repos_path):
    return repos_path / 'references'


@pytest.fixture(scope='session')
def bibfiles(references_path):
    return pyglottolog.references.BibFiles.from_path(references_path)


@pytest.fixture
def bibfiles_copy(tmp_path, references_path):
    references_copy = tmp_path / 'references'
    shutil.copytree(references_path, references_copy)
    return pyglottolog.references.BibFiles.from_path(references_copy)


@pytest.fixture(scope='session')
def hhtypes(references_path):
    return pyglottolog.references.HHTypes(references_path / 'hhtype.ini')


@pytest.fixture(scope='session')
def api(repos_path):
    """Glottolog instance from shared directory for read-only tests."""
    return pyglottolog.Glottolog(repos_path)


@pytest.fixture
def caching_api(repos_path):
    """Glottolog instance from shared directory for read-only tests."""
    return pyglottolog.Glottolog(repos_path, cache=True)


@pytest.fixture
def api_copy(tmp_path, repos_path):
    """Glottolog instance from isolated directory copy."""
    repos_copy = tmp_path / 'repos'
    shutil.copytree(repos_path, repos_copy)
    return pyglottolog.Glottolog(repos_copy)
