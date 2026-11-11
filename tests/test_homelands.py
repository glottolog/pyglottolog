import shutil

from pyglottolog import homelands
from pyglottolog.homelands import compute, Landmasses, md, recursive_centroids

try:
    from shapely.geometry import Point
except ImportError:  # pragma: no cover
    Point = None


def test_Landmasses():
    if homelands.GEO:  # pragma: no cover
        lm = Landmasses.from_geojson()
        assert lm.contain(Point(0.0, 33.0), ['europe.geojson'])


def test_compute(api_copy):
    if homelands.GEO:  # pragma: no cover
        assert compute(api_copy, md)
        assert compute(api_copy, recursive_centroids)

        abcd1233 = api_copy.tree / 'abcd1233'
        abcd1233.mkdir()
        abcd1233.joinpath('md.ini').write_text(
            '# -*- coding: utf-8 -*-\n[core]\nname = family0\nlevel = family')
        shutil.move(str(api_copy.tree / 'abcd1234'), str(abcd1233))

        assert compute(api_copy, md)
        assert compute(api_copy, recursive_centroids)
