import re
import functools
import collections

import requests
import attr

from csvw.dsv import reader
from clldutils.misc import nfilter
from clldutils.attrlib import valid_range

from .util import LinkProvider

BASE_URL = "http://endangeredlanguages.com"
CSV_URL = BASE_URL + "/userquery/download/"


def split(s, sep=';'):
    s = re.sub('"(?P<name>[^;]+);"', lambda m: '"{}";'.format(m.group('name').strip()), s)
    return nfilter(ss.strip() for ss in s.split(sep))


def parse_coords(s):
    cc = nfilter(ss.strip().replace(' ', '') for ss in re.split('[,;]', s))
    return [Coordinate(cc[i], cc[i + 1]) for i in range(0, len(cc), 2)]


@attr.s
class Coordinate(object):
    latitude = attr.ib(converter=lambda s: float(s.strip()), validator=valid_range(-90, 90))
    longitude = attr.ib(converter=lambda s: float(s.strip()), validator=valid_range(-180, 180))


@attr.s
class ElCatLanguage(object):
    id = attr.ib(converter=int)
    isos = attr.ib(converter=functools.partial(split, sep=','))
    name = attr.ib(converter=lambda s: s.strip())
    also_known_as = attr.ib(converter=split)
    status = attr.ib()
    speakers = attr.ib()
    classification = attr.ib()
    variants_and_dialects = attr.ib(converter=split)
    u = attr.ib()
    comment = attr.ib()
    countries = attr.ib(converter=split)
    continent = attr.ib()
    coordinates = attr.ib(converter=parse_coords)

    @property
    def names(self):
        return [self.name] + [n for n in self.also_known_as if n != self.name]

    @property
    def url(self):
        return BASE_URL + '/lang/{0.id}'.format(self)


def read():
    return [ElCatLanguage(*row) for row in reader(requests.get(CSV_URL).text.split('\n')) if row]


class ElCat(LinkProvider):
    def iterupdated(self, languoids):
        elcat_langs = collections.defaultdict(list)
        for line in read():
            for iso in line.isos:
                elcat_langs[iso].append(line)

        for lang in languoids:
            changed = False
            changed = False
            id_ = None
            # check for glottocode as ElCat.iso
            if lang.id in elcat_langs:
                id_ = lang.id
            # check for ISO code as ElCat.iso
            elif lang.iso in elcat_langs:
                id_ = lang.iso
            if id_ is not None:
                if lang.update_links(
                    'endangeredlanguages.com', [(l_.url, l_.name) for l_ in elcat_langs[id_]]
                ):
                    changed = True
                if len(elcat_langs[id_]) == 1:
                    # Only add alternative names, if only one ElCat language matches!
                    changed = lang.update_names(
                        elcat_langs[id_][0].names, type_='elcat') or changed
            else:
                changed = any([lang.update_links('endangeredlanguages.com', []),
                               lang.update_names([], type_='elcat')])

            if changed:
                yield lang
