"""
Create an HTML/Javascript map (using leaflet) of Glottolog languoids.
"""
import json
import string
import collections

from clldutils.color import qualitative_colors
from clldutils.path import git_describe
from clldutils.clilib import PathType

from pyglottolog.cli_util import add_output_dir


def register(parser):
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


def run(args):
    nodes = {n.id: n for n in args.repos.languoids()}
    legend = collections.Counter()
    glottocodes = args.glottocodes.read_text(encoding='utf8').split() if args.glottocodes else None

    langs = []
    for n in nodes.values():
        if ((glottocodes is None and n.level == args.repos.languoid_levels.language)
                or (glottocodes and n.id in glottocodes)) and n.latitude != None:  # noqa: W503
            fid = n.lineage[0][1] if n.lineage else n.id
            if (not nodes[fid].category.startswith('Pseudo')) or fid == n.id:
                langs.append((n, fid))
                legend.update([fid])

    color_map = [fid for fid, _ in legend.most_common()]
    color_map = dict(zip(color_map, qualitative_colors(len(color_map))))
    print(color_map)

    def l2f(t):
        n, fid = t
        lon, lat = n.longitude, n.latitude
        if lon <= -26:
            lon += 360  # make the map pacific-centered.

        return {
            "geometry": {"coordinates": [lon, lat], "type": "Point"},
            "id": n.id,
            "properties": {
                "name": n.name,
                "color": color_map[fid],
                "family": nodes[fid].name,
                "family_id": fid,
            },
            "type": "Feature"
        }

    def legend_item(fid, c):
        return \
            '<span style="background-color: {0}; border: 1px solid black;">'\
            '&nbsp;&nbsp;&nbsp;</span> '\
            '<a href="https://glottolog.org/resource/languoid/id/{1}">{2}</a> ({3})'.format(
                color_map[fid], fid, nodes[fid].name, c)

    geojson = {
        "features": list(map(l2f, langs)),
        "properties": {
            "legend": {
                fid: legend_item(fid, c) for fid, c in legend.most_common() if
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
            nlangs=len(langs)),
        encoding='utf8')
    print(html.resolve().as_uri())
