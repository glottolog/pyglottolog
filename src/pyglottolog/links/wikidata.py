"""
Query wikidata's SPARQL endpoint for info about Glottolog languoids identified by Glottocode.
"""
from csvw.dsv import reader
import requests

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


def iterupdated(languoids):
    res = requests.post(
        'https://query.wikidata.org/sparql',
        data=dict(query=SPARQL),
        headers=dict(Accept='text/csv')
    )
    res = {d['glottocode']: d for d in reader(res.text.split('\n'), dicts=True)}
    for l in languoids:
        changed = False
        if l.id in res:
            if l.update_link('www.wikidata.org', res[l.id]['item']):
                changed = True
            if res[l.id]['wikipedia'] and l.update_link('en.wikipedia.org', res[l.id]['wikipedia']):
                changed = True
        if changed:
            yield l
