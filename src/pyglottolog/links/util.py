import io
import json
import zipfile
import itertools
import collections

from csvw.dsv import reader
import requests
from pycldf.dataset import MD_SUFFIX


def read_cldf_languages(url):  # pragma: no cover
    r = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(r.content)) as zip:
        for member in zip.namelist():
            if member.endswith(MD_SUFFIX):
                break
        else:
            raise ValueError('No metadata file found')

        with zip.open(member) as fp:
            md = json.loads(fp.read().decode('utf8'))

        for table in md['tables']:
            if table.get('dc:conformsTo') == 'http://cldf.clld.org/v1.0/terms.rdf#LanguageTable':
                lurl, schema = table['url'], table['tableSchema']['columns']
                break
        else:
            raise ValueError('No LanguageTable found')

        for member in zip.namelist():
            if member.endswith(lurl):
                with zip.open(member) as fp:
                    return reader([l.strip() for l in fp.readlines()], dicts=True), schema
        else:
            raise ValueError('LanguageTable url not found in zip')


def read_grouped_cldf_languages(url):  # pragma: no cover
    langs, schema = read_cldf_languages(url)
    colmap, gccol = {}, None
    for col in schema:
        colmap[col['name']] = col.get('propertyUrl', col['name'])
        if col.get('propertyUrl') == 'http://cldf.clld.org/v1.0/terms.rdf#glottocode':
            gccol = col['name']

    if not gccol:
        raise ValueError('No glottocode column in LanguageTable')

    for gc, langs in itertools.groupby(sorted(langs, key=lambda d: d[gccol]), lambda d: d[gccol]):
        yield gc, [{colmap[k]: v for k, v in l.items()} for l in langs]


class LinkProvider(object):
    __domain__ = None
    __cldf_dataset_url__ = None
    __url_template__ = None
    __label_template__ = None

    def iterupdated(self, languoids):  # pragma: no cover
        if self.__domain__ and self.__cldf_dataset_url__ and self.__url_template__:
            # FIXME: Ideally, we'd want the CLDF data to specify full URLs for languages via a
            # valueUrl property on the ID column (or the LanguageTable?).
            res = collections.defaultdict(list)
            for gc, langs in read_grouped_cldf_languages(self.__cldf_dataset_url__):
                for lang in langs:
                    item = self.__url_template__.format(lang)
                    if self.__label_template__:
                        item = (item, self.__label_template__.format(lang))
                    res[gc].append(item)
            for l in languoids:
                if l.update_links(self.__domain__, res.get(l.id, [])):
                    yield l
        else:
            raise NotImplementedError()


class PHOIBLE(LinkProvider):  # pragma: no cover
    __domain__ = 'phoible.org'

    def __init__(self):
        r = requests.get('https://doi.org/10.5281/zenodo.2562766')
        record_id = r.url.split("/")[-1]
        r = requests.get('https://zenodo.org/api/records/%s' % record_id)
        self.__cldf_dataset_url__ = r.json()['files'][0]['links']['self']

    def iterupdated(self, languoids):  # pragma: no cover
        urls = {}
        for gc, langs in read_grouped_cldf_languages(self.__cldf_dataset_url__):
            urls[gc] = ['https://{0}/languages/{1}'.format(self.__domain__, gc)]
        for l in languoids:
            if l.update_links(self.__domain__, urls.get(l.id, [])):
                yield l


class APICS(LinkProvider):  # pragma: no cover
    __domain__ = "apics-online.info"
    __cldf_dataset_url__ = "https://cdstar.shh.mpg.de/bitstreams/" \
                           "EAEA0-61A2-213C-A9D8-0/apics_dataset.cldf.zip"
    __url_template__ = 'https://' + __domain__ + \
                       '/contributions/{0[http://cldf.clld.org/v1.0/terms.rdf#id]}'
    __label_template__ = '{0[http://cldf.clld.org/v1.0/terms.rdf#name]}'


class WALS(LinkProvider):  # pragma: no cover
    __domain__ = "wals.info"
    __cldf_dataset_url__ = "https://cdstar.shh.mpg.de/bitstreams/" \
                           "EAEA0-7269-77E5-3E10-0/wals_dataset.cldf.zip"
    __url_template__ = 'https://' + __domain__ + \
                       '/languoid/lect/wals_code_{0[http://cldf.clld.org/v1.0/terms.rdf#id]}'
    __label_template__ = '{0[http://cldf.clld.org/v1.0/terms.rdf#name]}'
