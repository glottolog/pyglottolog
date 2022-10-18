from pyglottolog.homelands import *


def test_compute(api):
    from pyglottolog import homelands
    if homelands.geo:  # pragma: no cover
        assert compute(api, md)
        assert compute(api, recursive_centroids)
