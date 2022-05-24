import io
import json
import pathlib
import collections

from csvw.dsv import reader, Dialect
import requests
from clldutils.misc import nfilter

from .util import LinkProvider

DOMAIN = 'collection.aiatsis.gov.au'
# The AIATSIS name data (see https://collection.aiatsis.gov.au/datasets/austlang/001)
MD_URL = "https://data.gov.au/data/dataset/70132e6f-259c-4e0f-9f95-4aed1101c053/resource/" \
         "e9a9ea06-d821-4b53-a05f-877409a1a19c/download/aiatsis_austlang_endpoint_001.csv"
# We get the mapping from AIATSIS to Glottolog from Chirila:
URL = 'http://chirila.yale.edu/languages'


class AIATSIS(LinkProvider):
    def iterupdated(self, languoids):  # pragma: no cover
        return
        res = reader(
            io.StringIO(requests.get(MD_URL).content.decode('utf-8-sig')),
            dialect=Dialect(skipBlankRows=True, commentPrefix='<'),
            dicts=True)
        md = {d['language_code']: d for d in res if 'language_code' in d}
        lmap = collections.defaultdict(set)
        for line in requests.get(URL).text.splitlines():
            if line.startswith('var curItem'):
                line = line.split('=', maxsplit=1)[1]
                d = json.loads(line)
                if d['AIATSIS_Code'] and d['Glottolog_ID']:
                    codes = [c.strip().replace('*', '') for c in d['AIATSIS_Code'].split(',')]
                    for code in codes:
                        if code:
                            if code not in md:
                                print(d['AIATSIS_Code'], list(md.keys())[:10])
                                continue
                            lmap[d['Glottolog_ID']].add(code)
        with pathlib.Path(__file__).parent.joinpath('aiatsis.json').open(encoding='utf8') as fp:
            for code, gc in json.load(fp).items():
                if code not in md:
                    print(code, list(md.keys())[:10])
                    continue
                lmap[gc].add(code)

        for lang in languoids:
            links, names = [], []
            for c in sorted(lmap.get(lang.id, [])):
                links.append((md[c]['uri'], md[c]['language_name']))
                if md[c]['language_name']:
                    names.append(md[c]['language_name'])
                names.extend(nfilter([n.strip() for n in md[c]['language_synonym'].split('|')]))
            if any([
                lang.update_links(DOMAIN, links),
                lang.update_names(names, type_='aiatsis'),
            ]):
                yield lang
