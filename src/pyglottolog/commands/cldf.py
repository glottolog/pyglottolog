"""
Dump Glottolog data as CLDF dataset
"""
import pathlib

from clldutils import jsonlib

from pyglottolog import cldf


def register(parser):
    parser.add_argument(
        'cldf_dir',
        type=pathlib.Path,
        help='path to clone of glottolog/glottolog-cldf')


def run(args):
    cldf.cldf(args.repos, args.cldf_dir, args.log)
    zenodo = jsonlib.load(args.repos.path('.zenodo.json'))
    zenodo['title'] = zenodo['title'].replace('/glottolog:', '/glottolog-cldf:') + ' as CLDF'
    zenodo['communities'].append(dict(identifier='cldf-datasets'))
    zenodo['keywords'].append('cldf:StructureDataset')
    jsonlib.dump(zenodo, args.cldf_dir.parent / '.zenodo.json', indent=4)
