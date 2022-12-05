import shutil

from pyglottolog.homelands import *


def test_compute(api_copy):
    from pyglottolog import homelands
    if homelands.geo:  # pragma: no cover
        assert compute(api_copy, md)
        assert compute(api_copy, recursive_centroids)

        abcd1233 = api_copy.tree / 'abcd1233'
        abcd1233.mkdir()
        abcd1233.joinpath('md.ini').write_text(
            '# -*- coding: utf-8 -*-\n[core]\nname = family0\nlevel = family')
        shutil.move(str(api_copy.tree / 'abcd1234'), str(abcd1233))

        assert compute(api_copy, md)
        assert compute(api_copy, recursive_centroids)
