import collections

import requests

from .util import LinkProvider


def iter_id_iso():  # pragma: no cover
    for i in range(3):
        data = requests.get(
            "http://crubadan.org/writingsystems",
            params={
                "sEcho": "1",
                "iDisplayStart": "{0}".format(1000 * i),
                "iDisplayLength": "1000",
                "iSortingCols": "1",
                "iSortCol_0": "1",
            },
            headers={"accept": "application/json", "x-requested-with": "XMLHttpRequest"},
        ).json()
        for row in data['aaData']:
            yield (row[1].strip(), row[2].strip())


# crubadan.org seems to no longer be operational
#class CRUBADAN(LinkProvider):
#    def iterupdated(self, languoids):  # pragma: no cover
#        lmap = collections.defaultdict(list)
#        for lid, iso in iter_id_iso():
#            lmap[iso].append(lid)
#        for lang in languoids:
#            links = ["http://crubadan.org/languages/" + c for c in lmap.get(lang.iso, [])]
#            if lang.update_links('crubadan.org', links):
#                yield lang
