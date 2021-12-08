import re
import functools
import collections

import requests
import attr

from csvw.dsv import reader
from clldutils.misc import nfilter
from clldutils.attrlib import valid_range

from .util import LinkProvider
from ..languoids import Country


BASE_URL = "https://endangeredlanguages.com"
DOMAIN = "endangeredlanguages.com"
CFG_ID_NAME = "endangeredlanguages"
LINK_TYPE = "elcat"
CSV_URL = BASE_URL + "/userquery/download/"

GLOTTOCODE_MAP = {
    'afta1234': 10069, 'alab1256': 943, 'algh1238': 944, 'alip1234': 7175, 'ampi1237': 1333,
    'anei1239': 10821, 'apol1242': 1574, 'apul1237': 10922, 'ashi1243': 1577, 'assy1241': 9329,
    'auve1239': 8630, 'avok1244': 10790, 'awia1234': 2030, 'bagh1249': 1584, 'bain1259': 1419,
    'bale1254': 8030, 'bana1283': 5679, 'bana1307': 1792, 'bang1335': 1588, 'bara1408': 1123,
    'bart1238': 1592, 'barz1241': 9290, 'bear1241': 1675, 'beni1249': 283, 'bhal1244': 1599,
    'bhum1234': 1601, 'bili1250': 5561, 'binb1242': 5554, 'bodi1253': 5929, 'boka1249': 1604,
    'boon1243': 6677, 'boto1248': 10488, 'brib1244': 7176, 'brun1247': 7177, 'burg1244': 1230,
    'bwen1239': 10792, 'camb1244': 10129, 'cata1288': 10853, 'cent2328': 8554, 'chak1275': 10920,
    'chir1296': 10733, 'chon1286': 7289, 'cola1237': 6693, 'cosa1234': 10709, 'cunn1236': 10720,
    'dale1238': 3189, 'dans1239': 10452, 'dark1243': 4106, 'demu1235': 1735, 'deng1252': 2145,
    'dger1238': 1863, 'diah1239': 5134, 'dirr1240': 10465, 'djuw1238': 6229, 'dukh1234': 3196,
    'duox1238': 10625, 'duun1241': 5727, 'dyar1234': 10450, 'east2774': 8552, 'efut1241': 1456,
    'fada1248': 5931, 'farv1234': 10726, 'fore1274': 3393, 'fung1247': 547, 'fuyu1243': 3383,
    'gall1275': 3412, 'ganj1241': 4612, 'gard1245': 946, 'gari1254': 5935, 'garm1244': 10840,
    'gasc1240': 8631, 'geji1246': 2346, 'gily1242': 8556, 'girr1240': 5712, 'gube1234': 1418,
    'hach1239': 10378, 'hams1239': 10109, 'hare1244': 2442, 'hill1258': 10414, 'huzh1238': 2088,
    'hwar1238': 6038, 'hwel1241': 6106, 'ikor1238': 8194, 'indo1291': 7185, 'jaba1234': 10839,
    'jarq1234': 10074, 'jows1234': 10722, 'jude1271': 10502, 'jude1276': 10499, 'kais1242': 3214,
    'kamd1238': 5998, 'kani1276': 6688, 'kark1255': 5641, 'kart1247': 6689, 'kash1276': 10500,
    'kaur1267': 5871, 'kesh1234': 10724, 'kham1281': 8234, 'khap1242': 5884, 'khuf1238': 6108,
    'komi1277': 3280, 'komn1238': 10748, 'kuhp1234': 10073, 'kuma1284': 10475, 'lang1309': 3391,
    'lang1321': 552, 'lang1332': 10463, 'lara1261': 8116, 'lawi1235': 6045, 'lenc1243': 7256,
    'leva1238': 5657, 'limo1246': 10461, 'liya1241': 5562, 'liya1242': 5549, 'lizu1234': 10624,
    'long1406': 10814, 'lopn1238': 10481, 'lush1256': 10462, 'maan1239': 5194, 'mand1418': 5563,
    'mans1258': 8529, 'many1256': 6696, 'mard1245': 2053, 'mayy1239': 5883, 'mbiy1238': 6700,
    'meym1234': 10071, 'midd1324': 1751, 'mila1245': 1378, 'minh1238': 10471, 'miny1239': 7172,
    'mith1236': 6704, 'mpra1235': 3725, 'mudb1240': 2550, 'muya1239': 5609, 'mwen1238': 1135,
    'mwin1241': 5049, 'nasv1234': 10789, 'nati1244': 2512, 'navw1234': 3065, 'nene1249': 2062,
    'nese1235': 2089, 'ngal1294': 5546, 'ngum1253': 6717, 'nisv1234': 10791, 'niti1249': 10795,
    'norm1245': 3284, 'nort3264': 8550, 'nucl1693': 10453, 'nyan1311': 534, 'oldb1247': 7187,
    'ongk1234': 8571, 'ordo1245': 10470, 'orig1234': 7006, 'orko1234': 10801, 'oros1238': 5866,
    'pada1257': 5677, 'pail1243': 7171, 'pena1270': 8741, 'phal1255': 5938, 'phon1243': 5874,
    'phut1246': 10746, 'picu1248': 6509, 'plai1258': 9011, 'poit1240': 3269, 'prov1235': 8629,
    'pudi1238': 5451, 'ramo1243': 5684, 'rats1237': 10309, 'rucc1239': 5876, 'ruku1239': 486,
    'rush1239': 5870, 'sadu1234': 10708, 'sakh1247': 2896, 'sama1296': 5173, 'sapw1237': 10424,
    'sede1245': 10847, 'shee1239': 5932, 'shim1250': 5691, 'shir1258': 10503, 'shir1268': 5048,
    'sich1239': 5811, 'sigi1234': 10495, 'solo1263': 8570, 'sout2962': 2091, 'sout3226': 8551,
    'sout3262': 8555, 'soyo1234': 10480, 'sure1238': 5695, 'taiw1247': 2805, 'tana1291': 8118,
    'tang1377': 7170, 'tazh1234': 5180, 'tazz1244': 8553, 'teja1235': 3114, 'tets1235': 8509,
    'teus1236': 2150, 'toum1239': 5872, 'tsix1234': 4570, 'tuha1234': 10479, 'tyem1238': 5947,
    'urim1252': 10568, 'urmi1249': 9289, 'viva1235': 945, 'vivt1234': 10794, 'vovo1238': 10797,
    'wail1244': 2174, 'wang1288': 6269, 'wara1302': 2707, 'wurl1240': 5452, 'xinc1242': 9709,
    'xinc1246': 6195, 'xink1235': 6196, 'yang1305': 5560, 'yara1254': 6806, 'yaww1238': 7173,
    'yazd1240': 10501, 'yila1234': 10717, 'yogy1234': 7193, 'yulp1239': 5245, 'yuwa1242': 5987,
    'zaks1239': 10489, 'zara1252': 10444, 'zefr1234': 10072, 'zemi1238': 1253, 'zoro1244': 1630,
    'zull1239': 10464,
}


def split(s, sep=';'):
    s = re.sub('"(?P<name>[^;]+);"', lambda m: '"{}";'.format(m.group('name').strip()), s)
    return nfilter(ss.strip() for ss in s.split(sep))


def lat(s):
    if s.endswith('S'):
        s = '-' + s[:-1]
    return s


def lon(s):
    if s.endswith('W'):
        s = '-' + s[:-1]
    return s


def parse_coords(s):
    cc = nfilter(ss.strip().replace(' ', '') for ss in re.split('[,;]', s))
    res = []
    for i in range(0, len(cc), 2):
        try:
            res.append(Coordinate(cc[i], cc[i + 1]))
        except ValueError:
            continue
    return res


@attr.s
class Coordinate(object):
    latitude = attr.ib(converter=lambda s: float(lat(s.strip())), validator=valid_range(-90, 90))
    longitude = attr.ib(converter=lambda s: float(lon(s.strip())), validator=valid_range(-180, 180))


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
        res = [self.name]
        for n in self.also_known_as:
            for nn in split(n, sep=','):
                if nn not in res:
                    res.append(nn)
        return res

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
            elcat_langs[line.id].append(line)

        for lang in languoids:
            changed = False
            id_ = None
            if lang.id in GLOTTOCODE_MAP:
                if GLOTTOCODE_MAP[lang.id] in elcat_langs:
                    id_ = GLOTTOCODE_MAP[lang.id]
                else:
                    print('GLOTTOCODE_MAP: [{}]: ElCat ID {} not known'.format(
                        lang.id, GLOTTOCODE_MAP[lang.id]))
            # check for glottocode as ElCat.iso
            elif lang.id in elcat_langs:
                id_ = lang.id
            # check for ISO code as ElCat.iso
            elif lang.iso in elcat_langs:
                id_ = lang.iso
            if id_ is not None:
                if lang.update_links(
                    DOMAIN, [(l_.url, l_.name) for l_ in elcat_langs[id_]]
                ):
                    changed = True
                if len(elcat_langs[id_]) == 1:
                    # Only add alternative names, if only one ElCat language matches!
                    changed = lang.update_names(
                        elcat_langs[id_][0].names, type_=LINK_TYPE) or changed

                    # Add missing coordinates
                    if not lang.latitude:
                        # Only add missing coordinates, if ElCat lists only one coordinate pair!
                        if elcat_langs[id_][0].coordinates\
                                and len(elcat_langs[id_][0].coordinates) == 1:
                            coords = elcat_langs[id_][0].coordinates[0]
                            lang.latitude = coords.latitude
                            lang.longitude = coords.longitude
                            changed = True

                    # Add missing countries
                    if not lang.countries and elcat_langs[id_][0].countries:
                        # Only add countries, if only one ElCat language matches!
                        new_countries = nfilter([Country.from_name(c)
                                                for c in set(elcat_langs[id_][0].countries)])
                        if new_countries:
                            lang.countries = new_countries
                            changed = True

                    # Sync ElCat links and identifier
                    new_identifiers = []
                    all_elcat_link_ids = [int(li.url.split('/')[-1]) for li in lang.links
                                          if li.domain == DOMAIN]
                    for id_ in all_elcat_link_ids:
                        if id_ in elcat_langs:
                            new_identifiers.append(str(id_))
                        else:
                            print('Sync ElCat links [{}]: ElCat ID {} not known'.format(
                                lang.id, id_))
                    if new_identifiers:
                        changed = True
                        if len(new_identifiers) == 1:
                            new_identifiers = new_identifiers[0]
                        if not lang.identifier:
                            lang.cfg['identifier'] = {}
                        lang.cfg['identifier'][CFG_ID_NAME] = new_identifiers
            else:
                changed = any([lang.update_links(DOMAIN, []),
                               lang.update_names([], type_=LINK_TYPE)])

            if changed:
                yield lang

    # --- for admin purposes only ---
    def check_coverage(self, languoids):  # pragma: no cover
        elcat_langs = collections.defaultdict(list)
        elcat_ids = set()
        seen_elcat_ids = set()
        for line in read():
            for iso in line.isos:
                elcat_langs[iso].append(line)
            elcat_langs[line.id].append(line)
            elcat_ids.add(line.id)

        for lang in languoids:
            id_ = None
            if lang.id in GLOTTOCODE_MAP:
                if GLOTTOCODE_MAP[lang.id] in elcat_langs:
                    id_ = GLOTTOCODE_MAP[lang.id]
                else:
                    print('GLOTTOCODE_MAP: [{}]: ElCat ID {} not known'.format(
                        lang.id, GLOTTOCODE_MAP[lang.id]))
            # check for glottocode as ElCat.iso
            elif lang.id in elcat_langs:
                id_ = lang.id
            # check for ISO code as ElCat.iso
            elif lang.iso in elcat_langs:
                id_ = lang.iso
            if id_ is not None:
                seen_elcat_ids |= set([e.id for e in elcat_langs[id_]])

        print('Matched {} of {} ElCat languoids'.format(len(seen_elcat_ids), len(elcat_ids)))
        print('Non-matches:')
        for elcat_id in list(elcat_ids - seen_elcat_ids):
            for el in elcat_langs[elcat_id]:
                print('\t'.join(
                    [el.name, ','.join(el.isos), '{}/lang/{}'.format(BASE_URL, elcat_id)]))
