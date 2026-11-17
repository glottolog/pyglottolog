"""
Create an HTML/Javascript map (using leaflet) of Glottolog languoids.

Languoids to plot can be specified as glottocodes or comma-separated
"glottocode,latitude,longitude" triples in a file or as stdin.
"""
import sys
import json
import string
import pathlib
import argparse
import functools
import webbrowser
import collections
import dataclasses
from typing import Self

from clldutils.color import qualitative_colors
from clldutils.path import git_describe
from clldutils.clilib import PathType

from pyglottolog.cli_util import add_output_dir
from pyglottolog.languoids import Languoid, LanguoidMapType

CoordinatesMap = dict[str, tuple[float | None, float | None]]


def register(parser):  # pylint: disable=C0116
    add_output_dir(parser)
    parser.add_argument(
        '--glottocodes',
        help='File listing Glottocodes the map should be restricted to',
        type=PathType(type='file'),
        default=None,
    )
    parser.add_argument(
        '--min-langs-for-legend',
        help='minimum number of languages in a family for a map legend entry',
        type=int,
        default=10,
    )
    parser.add_argument(
        '--open',
        action='store_true',
        default=False,
        help='open the map in a web browser after',
    )


def _get_glottocodes(spec: pathlib.Path | None, test: bool = False) -> CoordinatesMap:
    """Glottocodes for languoids to display on the map can be specified in various ways."""
    glottocodes = []
    if spec:
        glottocodes = spec.read_text(encoding='utf8').split()
    elif not test:  # pragma: no cover
        glottocodes = [line.strip() for line in sys.stdin.readlines()]
    res = {}
    for gc in glottocodes:
        if ',' in gc:
            gc, lat, lon = gc.split(',')
            res[gc] = (float(lat) if lat else None, float(lon) if lon else None)
        else:
            res[gc] = (None, None)
    return res


def _include_node(n, glottocodes: CoordinatesMap, languoid_levels):
    if any((not glottocodes and n.level == languoid_levels.language,
            glottocodes and n.id in glottocodes)):
        if n.latitude is not None or glottocodes.get(n.id, (None,))[0] is not None:
            return True
    return False


@dataclasses.dataclass(frozen=True)
class MapData:
    langs: list[tuple[Languoid, str]]
    legend: collections.Counter

    @classmethod
    def from_nodemap(cls, nodes: LanguoidMapType, glottocodes: CoordinatesMap, llevels) -> Self:
        langs = []
        legend = collections.Counter()
        for n in nodes.values():
            if _include_node(n, glottocodes, llevels):
                fid = n.lineage[0][1] if n.lineage else n.id
                if (not nodes[fid].category.startswith('Pseudo')) or fid == n.id:
                    langs.append((n, fid))
                    legend.update([fid])
        return cls(langs, legend)

    @functools.cached_property
    def color_map(self):
        cm = [fid for fid, _ in self.legend.most_common()]
        return dict(zip(cm, qualitative_colors(len(cm))))


def run(args: argparse.Namespace):  # pylint: disable=C0116
    glottocodes = _get_glottocodes(args.glottocodes, args.test)
    nodes = {n.id: n for n in args.repos.languoids()}

    mdata = MapData.from_nodemap(nodes, glottocodes, args.repos.languoid_levels)

    def l2f(t):
        n, fid = t
        lat, lon = glottocodes.get(n.id, (None, None))
        if lat is None:
            lat = n.latitude
        if lon is None:
            lon = n.longitude
        if lon <= -26:
            lon += 360  # make the map pacific-centered.

        return {
            "geometry": {"coordinates": [lon, lat], "type": "Point"},
            "id": n.id,
            "properties": {
                "name": n.name,
                "color": mdata.color_map[fid],
                "family": nodes[fid].name,
                "family_id": fid,
            },
            "type": "Feature"
        }

    def legend_item(fid, c) -> str:
        return (f'<span style="background-color: {mdata.color_map[fid]}; border: 1px solid black;">'
                f'&nbsp;&nbsp;&nbsp;</span> '
                f'<a href="https://glottolog.org/resource/languoid/id/{fid}">{nodes[fid].name}</a> '
                f'({c})')

    geojson = {
        "features": [l2f(lg) for lg in mdata.langs],
        "properties": {
            "legend": {
                fid: legend_item(fid, c) for fid, c in mdata.legend.most_common() if
                c >= args.min_langs_for_legend},
        },
        "type": "FeatureCollection"
    }

    def rendered_template(name, **kw):
        return string.Template(
            args.pkg_dir.joinpath('templates', 'htmlmap', name).read_text(encoding='utf8')
        ).substitute(**kw)

    jsname = 'glottolog_map.json'
    args.output.joinpath(jsname).write_text(
        rendered_template('htmlmap.js', geojson=json.dumps(geojson, indent=4)), encoding='utf8')
    html = args.output.joinpath('glottolog_map.html')
    html.write_text(
        rendered_template(
            'htmlmap.html',
            version=git_describe(args.repos.repos),
            jsname=jsname,
            nlangs=len(mdata.langs)),
        encoding='utf8')
    print(html.resolve().as_uri())
    if args.open:
        webbrowser.open(str(html))  # pragma: no cover
