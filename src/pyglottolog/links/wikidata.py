"""
Query wikidata's SPARQL endpoint for info about Glottolog languoids identified by Glottocode.
"""
from csvw.dsv import reader
import requests

from .util import LinkProvider

SPARQL = """\
prefix schema: <http://schema.org/>
SELECT ?item ?glottocode ?wikipedia WHERE {
    ?item wdt:P1394 ?glottocode.
    OPTIONAL {
        ?wikipedia schema:about ?item .
        ?wikipedia schema:inLanguage "en" .
        FILTER (SUBSTR(str(?wikipedia), 1, 25) = "https://en.wikipedia.org/")
    }
}"""


class Wikidata(LinkProvider):
    def iterupdated(self, languoids):
        res = requests.post(
            'https://query.wikidata.org/sparql',
            data=dict(query=SPARQL),
            headers=dict(Accept='text/csv')
        )
        res = {d['glottocode']: d for d in reader(res.text.split('\n'), dicts=True)}
        for l in languoids:
            urls = {
                'www.wikidata.org': [
                    res[l.id]['item'].replace('http:', 'https:')] if l.id in res else [],
                'en.wikipedia.org': [
                    res[l.id]['wikipedia']] if (l.id in res) and res[l.id]['wikipedia'] else [],
            }
            if any([l.update_links(d, u) for d, u in urls.items()]):
                # Note: We must use list comprehension rather than a generator as first argument
                # to `any` to make sure `update_links` is called for each item in urls!
                yield l
