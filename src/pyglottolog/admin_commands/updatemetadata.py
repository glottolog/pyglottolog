"""
Update metadata.json from config/publication.ini
"""
import json
import configparser

from clldutils.metadata import Metadata


def run(args):  # pragma: no cover
    cfg = configparser.ConfigParser()
    cfg.read(str(args.repos.path('config', 'publication.ini')))
    md = {'title' if k == 'name' else k: v for k, v in cfg['web'].items()}
    md['publisher.contact'] = cfg['web']['contact']
    for k in ['publisher', 'license']:
        md.update(**{k + '.' + kk: v for kk, v in cfg[k].items()})

    args.repos.path('metadata.json').write_text(
        json.dumps(Metadata.from_jsonld({}, defaults=md).to_jsonld(), indent=2))
