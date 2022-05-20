import itertools
import collections

from clldutils.path import TemporaryDirectory
from pycldf.dataset import Dataset
import cldfzenodo


def read_grouped_cldf_languages(doi):  # pragma: no cover
    rec = cldfzenodo.Record.from_doi(doi)
    with TemporaryDirectory() as tmp:
        ds = Dataset.from_metadata(rec.download_dataset(tmp))
        langs = sorted(
            ds.iter_rows('LanguageTable', 'id', 'glottocode', 'name'),
            key=lambda r: r['glottocode'] or '')

    for gc, langs in itertools.groupby(langs, lambda d: d['glottocode']):
        yield gc, list(langs)


class LinkProvider(object):
    __domain__ = None
    __doi__ = None
    __url_template__ = None
    __label_template__ = None

    def __init__(self, repos=None):
        self.repos = repos

    def iterupdated(self, languoids):  # pragma: no cover
        if self.__domain__ and self.__doi__ and self.__url_template__:
            # FIXME: Ideally, we'd want the CLDF data to specify full URLs for languages via a
            # valueUrl property on the ID column (or the LanguageTable?).
            res = collections.defaultdict(list)
            for gc, langs in read_grouped_cldf_languages(self.__doi__):
                for lang in langs:
                    lang = {k: v.strip() if isinstance(v, str) else v for k, v in lang.items()}
                    item = self.__url_template__.format(lang)
                    if self.__label_template__:
                        item = (item, self.__label_template__.format(lang))
                    res[gc].append(item)
            for lang in languoids:
                if lang.update_links(self.__domain__, res.get(lang.id, [])):
                    yield lang
        else:
            raise NotImplementedError()


class PHOIBLE(LinkProvider):  # pragma: no cover
    __domain__ = 'phoible.org'
    __doi__ = '10.5281/zenodo.2562766'

    def iterupdated(self, languoids):  # pragma: no cover
        urls = {}
        for gc, langs in read_grouped_cldf_languages(self.__doi__):
            urls[gc] = ['https://{0}/languages/{1}'.format(self.__domain__, gc)]
        for lang in languoids:
            if lang.update_links(self.__domain__, urls.get(lang.id, [])):
                yield lang


class APICS(LinkProvider):  # pragma: no cover
    __domain__ = "apics-online.info"
    __doi__ = '10.5281/zenodo.3823887'
    __url_template__ = 'https://' + __domain__ + '/contributions/{0[id]}'
    __label_template__ = '{0[name]}'


class WALS(LinkProvider):  # pragma: no cover
    __domain__ = "wals.info"
    __doi__ = '10.5281/zenodo.3606197'
    __url_template__ = 'https://' + __domain__ + '/languoid/lect/wals_code_{0[id]}'
    __label_template__ = '{0[name]}'
