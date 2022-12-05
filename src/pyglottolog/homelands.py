"""
Computing geo-coordinates for homelands of language groups, i.e. languoids of level `family`.

Various ways of computing "homelands" for language groups have been proposed in the literature
since Sapir 1916. This module provides implementations of some of the simpler algorithms.
"""
import gzip
import json
import random
import typing
import decimal
import pathlib
import collections

try:
    from shapely.geometry import shape, GeometryCollection, MultiPoint, Point
    from shapely.ops import nearest_points
    import pyproj
    geo = True
except ImportError:  # pragma: no cover
    geo = False

import pyglottolog
from pyglottolog.languoids import Languoid

__all__ = ['compute', 'md', 'recursive_centroids']
random.seed(12345)


def _worlds_land_masses_dict():
    res = {}
    for p in pathlib.Path(pyglottolog.__file__).parent.joinpath('data').glob('*.geojson.gz'):
        with gzip.open(p, mode='rt', encoding='utf8') as fp:
            res[p.stem] = GeometryCollection([
                shape(f["geometry"]).buffer(0) for f in json.loads(fp.read())['features']])
    return res


def compute(api: pyglottolog.Glottolog,
            method: typing.Callable[
                [typing.List[Languoid]],
                typing.Dict[str, typing.Tuple[decimal.Decimal, decimal.Decimal]]])\
        -> typing.Dict[str, typing.Tuple[decimal.Decimal, decimal.Decimal]]:
    """
    Compute homelands for applicable Glottolog subgroups using a method implemented in this module
    or any callable with appropriate signature.
    """
    if not geo:  # pragma: no cover
        raise ValueError('Computing homelands requires the "geo" extra, installed via '
                         '"pip install pyglottolog[geo]"')
    return method(_l1_languages_with_coordinates(api))


def geodist(geod, p1, p2):
    return geod.inv(p1[1], p1[0], p2[1], p2[0])[2]


def md(langs: typing.List[Languoid])\
        -> typing.Dict[str, typing.Tuple[decimal.Decimal, decimal.Decimal]]:
    """
    Compute homeland coordinates for a language group (and its subgroups) as described as
    "md" method in "Testing methods of linguistic homeland detection using synthetic data"
    by Søren Wichmann and Taraka Rama
    https://doi.org/10.1098/rstb.2020.0202

    Wichmann and Rama 2021:

        In the third approach, abbreviated ‘md’ for ‘minimal distance’, we compute the average
        distance (as the crow flies) from each language to all the other languages. The location
        of the language that has the smallest average distance to the others is equated with the
        homeland.

    We use the `pyproj.Geod.inv` method to compute the great-circle distance between two points.

    .. seealso: https://pyproj4.github.io/pyproj/stable/api/geod.html
    """
    # Compute minimal distances per group:
    geod = pyproj.Geod(ellps='WGS84')

    grouped_languages = collections.defaultdict(list)
    for lang in langs:
        for _, gc, _ in lang.lineage:
            grouped_languages[gc].append(lang)

    homelands = {}
    for group, lgs in grouped_languages.items():
        if len(lgs) == 1:  # pragma: no cover
            homelands[group] = (lgs[0].latitude, lgs[0].longitude)
            continue

        # We shuffle the coordinates to avoid returning the first minimal-distance location in the
        # given order.
        coords = [(lg.latitude, lg.longitude) for lg in lgs]
        random.shuffle(coords)
        mindist, mincoord = None, None
        for i, coord in enumerate(coords):
            dist = sum(geodist(geod, coord, p) for j, p in enumerate(coords) if i != j)
            if (mindist is None) or (dist < mindist):
                mindist, mincoord = dist, coord
        homelands[group] = mincoord
    return homelands


def recursive_centroids(langs: typing.List[Languoid])\
        -> typing.Dict[str, typing.Tuple[decimal.Decimal, decimal.Decimal]]:
    """
    Recursively compute homelands of subgroups from the homelands of their immediate children in
    the classification.

    1. The homeland of a single language is its geographic coordinate.
    2. The homeland of a set of coordinates (for homelands or languages) is computed as
       nearest point on land of the centroid of the convex hull for the set of coordinates.
    """
    # We compute centroids with shapely in a projection-agnostic way. Thus, we have to make sure
    # to deal with longitudes wrapping around at 180° - which only happens for subgroups of
    # Austronesian.
    def pos_lon(lon, tlgc):
        return lon + 360 if lon < 0 and tlgc == 'aust1307' else lon

    def norm_lon(lon, tlgc):
        return lon - 360 if lon > 180 and tlgc == 'aust1307' else lon

    subgroups = collections.defaultdict(list)
    pref_continents = None
    for lang in langs:
        if not pref_continents:
            pref_continents = {
                'South America': ['southamerica', 'northaerica'],
                'North America': ['northamerica', 'southamerica'],
                'Eurasia': ['asia', 'europe'],
                'Africa': ['africa'],
                'Papunesia': ['oceania'],
                'Australia': ['oceania'],
            }[lang.macroareas[0].name]
        tlgc = lang.lineage[0][1]
        prev = None
        for i, (_, gc, _) in enumerate(reversed(lang.lineage)):
            if i == 0:  # For the immediate parent, we append the coordinate.
                subgroups[(tlgc, gc)].append((lang.latitude, lang.longitude))
            else:  # Otherwise we append the Glottocode of the immediate child.
                subgroups[(tlgc, gc)].append(prev)
            prev = gc

    geod = pyproj.Geod(ellps='WGS84')
    continents = _worlds_land_masses_dict()
    homelands = {}
    while subgroups:
        for (tlgc, gc), coords in list(subgroups.items()):
            # coords is a list of immediate children of the group specified by `gc`, either
            # given as coordinates of languages or homelands or as glottocodes.
            coords = [homelands.get(v, v) for v in coords]
            if any(isinstance(v, str) for v in coords):
                # There are still unresolved homelands for the immediate children. Defer
                # computation until all homelands of children are resolved.
                continue  # pragma: no cover
            # Compute the homeland from the homelands of the children.
            homeland = MultiPoint(
                [(pos_lon(p[1], tlgc), p[0]) for p in coords]).convex_hull.centroid
            homeland = Point(norm_lon(homeland.x, tlgc), homeland.y)
            for _, l in sorted(
                    continents.items(), key=lambda i: i[0] in pref_continents, reverse=True):
                if l.contains(homeland):
                    break  # pragma: no cover
            else:
                nps = [nearest_points(c, homeland)[0] for c in continents.values()]
                nps = [(p, geodist(geod, (p.y, p.x), (homeland.y, homeland.x))) for p in nps]
                homeland = sorted(nps, key=lambda n: n[1])[0][0]
            homelands[gc] = (homeland.y, homeland.x)
            del subgroups[(tlgc, gc)]
    return homelands


def _l1_languages_with_coordinates(api):
    invalid_macroareas = {
        'atla1278': {api.macroareas.northamerica.name},
        'aust1307': {api.macroareas.southamerica.name},
        'indo1319': {
            api.macroareas.northamerica.name,
            api.macroareas.southamerica.name,
            api.macroareas.africa.name,
            api.macroareas.australia.name,
            api.macroareas.pacific.name,
        },
    }
    return [
        lg for lg in api.languoids()
        if lg.latitude is not None
        and lg.lineage  # noqa: W503
        and lg.level == api.languoid_levels.language  # noqa: W503
        and lg.category == api.language_types.spoken_l1.category  # noqa: W503
        and (  # noqa: W503
            (lg.lineage[0][1] not in invalid_macroareas) or  # noqa: W504
            (not invalid_macroareas[lg.lineage[0][1]].intersection(ma.name for ma in lg.macroareas))
        )
    ]


if __name__ == '__main__':  # pragma: no cover
    from pyglottolog import Glottolog
    import sys

    gl = Glottolog(sys.argv[1], cache=True)
    res = compute(gl, md)
    print(len(res))
