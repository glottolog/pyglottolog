"""
Integrate data from ELCat's CLDF dataset into Glottolog.
"""
import re
import datetime
import itertools
import collections
import typing

from pycldf import Dataset
from pycldf.orm import Language

from pyglottolog.languoids.models import Country, Glottocode
from .util import LinkProvider

CFG_ID_NAME = "endangeredlanguages"
DOMAIN = "{}.com".format(CFG_ID_NAME)
LINK_TYPE = "elcat"
CLDF_DATASET = "https://raw.githubusercontent.com/" \
               "cldf-datasets/elcat/main/cldf/StructureDataset-metadata.json"


def format_comment(ellang: Language, lei: typing.Union[dict, str]) -> str:
    comment = "{} ({}{}) = {}".format(
        ellang.cldf.name,
        ellang.id,
        '-{}'.format(ellang.cldf.iso639P3code) if ellang.cldf.iso639P3code else '',
        (lei['Value'] if isinstance(lei, dict) else lei).replace('()', '').strip(),
    )
    if isinstance(lei, dict):
        if lei['Comment']:
            comment += ' ({})'.format(lei['Comment'])
        if lei['Source']:
            comment += ' [{}]({})'.format(
                lei['Source'][0].refkey(year_brackets=None), 'elcat:' + lei['Source'][0].id)
    return comment


def format_date() -> str:
    return datetime.datetime.now().isoformat().split('.')[0]


class ElCat(LinkProvider):
    __inactive__ = True
    status_map = {}

    def __init__(self, repos=None):
        LinkProvider.__init__(self, repos=repos)
        self.languages = collections.defaultdict(list)
        cldf = Dataset.from_metadata(CLDF_DATASET)
        self.lei = {}
        for lg in cldf.objects('LanguageTable', Language):
            if lg.cldf.glottocode:
                self.languages[lg.cldf.glottocode].append(lg)
            elif 'Glottolog' in lg.data['code_authorities']:
                for code in lg.data['codes']:
                    if Glottocode.pattern.match(code):
                        self.languages[code].append(lg)
            elif 'ISO 639-3' in lg.data['code_authorities']:
                for code in lg.data['codes']:
                    if re.fullmatch('[a-z]{3}', code):
                        self.languages[code].append(lg)
            self.lei[lg.id] = lg.data['endangerment']
        self.status_map = {}
        for status in self.repos.aes_status.values():
            for name in status.elcat.split('/'):
                self.status_map[name] = status
        for (lid, pid), rows in itertools.groupby(
            sorted(
                cldf.iter_rows('ValueTable'), key=lambda r: (r['Language_ID'], r['Parameter_ID'])),
            lambda r: (r['Language_ID'], r['Parameter_ID'])
        ):
            if pid == 'LEI':
                rows = list(rows)
                stati = []
                for row in rows:
                    stati.append(self.map_status(row['Value']).name)
                    if (((self.lei[lid] is None)
                         or (stati[-1] == self.map_status(self.lei[lid]).name))  # noqa W503
                            and (row['preferred'] is True)):  # noqa W504
                        row['Source'] = [cldf.sources[src] for src in row['Source']]
                        self.lei[lid] = row
                        break
                else:
                    # We pick the first source reporting the same status as the one chosen by ELCat
                    # overall as reference:
                    for i, status in enumerate(stati):
                        if status == self.lei[lid]:
                            rows[i]['Source'] = [cldf.sources[src] for src in rows[i]['Source']]
                            self.lei[lid] = rows[i]

    def map_status(self, s):
        if s:
            return self.status_map[s.split('(')[0].strip().lower()]

    def iterupdated(self, languoids):
        for lang in languoids:
            changed, ellangs = False, []
            if lang.id in self.languages:
                ellangs = self.languages[lang.id]
            elif lang.iso and (lang.iso in self.languages):
                ellangs = self.languages[lang.iso]

            if ellangs:  # There are ELCat languages mapped to the Glottolog languoid.
                changed = lang.update_links(DOMAIN, [(l_.valueUrl(), l_.name) for l_ in ellangs])

                countries = {c for c in itertools.chain(*[l_.data['Countries'] for l_ in ellangs])}
                existing = {c.id for c in lang.countries}
                if not countries.issubset(existing):
                    lang.countries = [Country.from_id(c) for c in sorted(countries.union(existing))]
                    changed = True

                if len(ellangs) != 1:
                    # Assign best case status as multiple ELCat varieties mapped to one languoid
                    # means ELCat describes dialects. Then the entire language is as endangered as
                    # the least endangered dialect.
                    try:
                        ellang = sorted(
                            [lg for lg in ellangs if lg.data['endangerment']],
                            key=lambda e: self.map_status(e.data['endangerment']))[0]
                    except IndexError:
                        ellang = ellangs[0]
                else:
                    ellang = ellangs[0]
                    # Only add alternative names, if only one ElCat language matches!
                    changed = lang.update_names(
                        [ellang.cldf.name] + ellang.data['alt_names'], type_=LINK_TYPE) or changed

                    # Add missing coordinates
                    if (not lang.latitude) and ellang.cldf.latitude and ellang.cldf.longitude:
                        # Only add missing coordinates, if ElCat lists only one coordinate pair!
                        lang.latitude = ellang.cldf.latitude
                        lang.longitude = ellang.cldf.longitude
                        changed = True

                lei = self.lei[ellang.id]
                value = None
                if isinstance(lei, dict):
                    value = lei
                    lei = lei['Value']

                if lang.endangerment:
                    if lang.endangerment.source.id == 'ElCat':
                        if lei is None:
                            del lang.cfg['endangerment']
                        else:
                            lang.cfg['endangerment']['status'] = self.map_status(lei).name
                            lang.cfg['endangerment']['date'] = format_date()
                            lang.cfg['endangerment']['comment'] = format_comment(
                                ellang, value or lei)
                        changed = True
                elif self.map_status(lei):
                    lang.cfg['endangerment'] = dict(
                        status=self.map_status(lei).name,
                        date=format_date(),
                        comment=format_comment(ellang, value or lei),
                        source='ElCat')
                    changed = True

            else:
                changed = any([lang.update_links(DOMAIN, []),
                               lang.update_names([], type_=LINK_TYPE)])

            if changed:
                yield lang
