"""
Fix macroarea GeoJSON
"""
import json
import collections

from clldutils.jsonlib import dump


def fixed(d, name):  # pragma: no cover
    if name in ['papunesia', 'eurasia']:
        new = None
        coordinates = []
        for polygon in d['coordinates']:
            polygon = polygon[0]

            if ([-180.0, -90.0] in polygon) or ([-180.0, 90.0] in polygon):
                # This polygon must be attached to the big one at the longitude 180 seam!
                for point in polygon:
                    point[0] = point[0] + 360
                # Now we re-order such that the polygon starts at 180,+.. and ends at 180,-90
                end, seam, start, after_bottom_left = [], [], [], False
                for point in polygon:
                    if point[0] != 180:
                        (start if after_bottom_left else end).append(point)
                    else:
                        after_bottom_left = True
                        seam.append(point)
                new = [seam[-1]] + start + end + [seam[0]]
                polygon = None
            elif ([180.0, -90.0] in polygon) or ([180.0, 90.0] in polygon):
                # The big one!
                points, in_seam = [], False
                for point in polygon:
                    if point[0] == 180.0:
                        if not in_seam:
                            points.append(point)
                            points.extend(new)
                        else:
                            print('skipping', point)
                        in_seam = True
                    else:
                        points.append(point)
                polygon = points

            if polygon:
                coordinates.append([polygon])
        d['coordinates'] = coordinates
    return d


def run(args):  # pragma: no cover
    for p in args.repos.path('config', 'macroareas', 'voronoi').glob('*.geojson'):
        with p.open(encoding='utf-8-sig') as fp:
            d = json.load(fp, object_pairs_hook=collections.OrderedDict)
        dump(fixed(d, p.stem), p, indent=4)
