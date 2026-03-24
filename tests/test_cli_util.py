import logging

from pyglottolog.cli_util import LanguoidStats
from pyglottolog.languoids import Languoid


def test_LanguoidStats(api_copy):
    stats = LanguoidStats.from_json(api_copy)
    assert len(stats.language) == 0
    stats.update(api_copy.languoid('abcd1235'))
    stats.to_json(api_copy)
    stats = LanguoidStats.from_json(api_copy)
    assert len(stats.language) == 1

    stats = LanguoidStats.from_tree(api_copy)
    assert len(stats.language) > 1


def test_LanguoidStats_check(api_copy, caplog, tmp_path):
    stats = LanguoidStats.from_json(api_copy)
    stats.update(api_copy.languoid('abcd1235'))

    # Fake removal of a language:
    lang = Languoid.from_name_id_level(tmp_path, 'name', 'abcd1238', None)
    lang._api = api_copy
    lang.level = api_copy.languoid_levels.language
    stats.update(lang)
    stats.check(api_copy, logging.getLogger(__name__))
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == 'ERROR'

    # Fake demotion of a language to a dialect:
    stats.update(api_copy.languoid('abcd1236'))
    stats.language.append(stats.dialect.pop())
    stats.check(api_copy, logging.getLogger(__name__))
    assert 'WARNING' in {rec.levelname for rec in caplog.records}
