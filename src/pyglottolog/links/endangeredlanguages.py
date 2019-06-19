# coding: utf8
from __future__ import unicode_literals, print_function, division
import re
import itertools

import requests
import attr

from csvw.dsv import reader
from clldutils.misc import nfilter
from clldutils.attrlib import valid_range

BASE_URL = "http://endangeredlanguages.com"
CSV_URL = BASE_URL + "/userquery/download/"


def split(s, sep=';'):
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
    iso = attr.ib()
    name = attr.ib()
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
    def url(self):
        return BASE_URL + '/lang/{0.id}'.format(self)


def read():
    return [ElCatLanguage(*row) for row in reader(requests.get(CSV_URL).text.split('\n')) if row]


def iterupdated(languoids):
    elcat_langs = {l.iso: l for l in read()}
    for l in languoids:
        changed = False
        if l.iso and l.iso in elcat_langs:
            elcat_lang = elcat_langs[l.iso]
            if l.update_link('endangeredlanguages.com', elcat_lang.url):
                changed = True
            names = set(itertools.chain(*l.names.values()))
            for name in [elcat_lang.name] + elcat_lang.also_known_as:
                if name not in names:
                    l.add_name(name, 'ElCat')
                    changed = True
        if changed:
            yield l
