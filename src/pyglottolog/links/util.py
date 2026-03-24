"""
LinkProvider implementations.
"""
import itertools
import collections
from collections.abc import Generator, Iterable

from clldutils.path import TemporaryDirectory
import cldfzenodo

from pyglottolog.languoids import Languoid


def read_grouped_cldf_languages(doi):
    """Read language information from CLDF datasets."""
    rec = cldfzenodo.Record.from_concept_doi(doi)
    with TemporaryDirectory() as tmp:
        ds = rec.download_dataset(tmp)
        langs = sorted(
            ds.iter_rows('LanguageTable', 'id', 'glottocode', 'name'),
            key=lambda r: r['glottocode'] or '')

    for gc, langs in itertools.groupby(langs, lambda d: d['glottocode']):
        yield gc, list(langs)


class LinkProvider:  # pylint: disable=R0903
    """
    Glottolog includes links from languoid's info pages to related info on other sites.
    Some of this info is curated by Glottolog, but most of it is aggregated from links included
    in the other resource. Extracting this information is the job of a `LinkProvider`.
    """
    __domain__ = None
    __doi__ = None
    __url_template__ = None
    __label_template__ = None

    def __init__(self, repos=None):
        self.repos = repos

    def iterupdated(self, languoids: Iterable[Languoid]) -> Generator[Languoid, None, None]:
        """Run through the proposed links and update languoids as needed."""
        if self.__domain__ and self.__doi__ and self.__url_template__:
            res = collections.defaultdict(list)
            for gc, langs in read_grouped_cldf_languages(self.__doi__):
                for lang in langs:
                    lang = {k: v.strip() if isinstance(v, str) else v for k, v in lang.items()}
                    item = self.__url_template__.format(lang)
                    if self.__label_template__:
                        item = (item, self.__label_template__.format(lang).split('[')[0].strip())
                    res[gc].append(item)
            for lang in languoids:
                if lang.update_links(self.__domain__, res.get(lang.id, [])):
                    yield lang
        else:
            raise NotImplementedError()  # pragma: no cover


class Test(LinkProvider):
    def iterupdated(self, languoids: Iterable[Languoid]) -> Generator[Languoid, None, None]:
        for lang in languoids:
            yield lang
            break


class PHOIBLE(LinkProvider):  # pragma: no cover  # pylint: disable=R0903,C0115
    __domain__ = 'phoible.org'
    __doi__ = '10.5281/zenodo.2562766'

    def iterupdated(self, languoids):  # pragma: no cover
        urls = {}
        for gc, _ in read_grouped_cldf_languages(self.__doi__):
            urls[gc] = [f'https://{self.__domain__}/languages/{gc}']
        for lang in languoids:
            if lang.update_links(self.__domain__, urls.get(lang.id, [])):
                yield lang


class WALS(LinkProvider):  # pragma: no cover  # pylint: disable=R0903,C0115
    __domain__ = "wals.info"
    __doi__ = '10.5281/zenodo.3606197'
    __url_template__ = 'https://' + __domain__ + '/languoid/lect/wals_code_{0[id]}'
    __label_template__ = '{0[name]}'


class Grambank(LinkProvider):  # pragma: no cover  # pylint: disable=R0903,C0115
    __inactive__ = True
    __domain__ = "grambank.clld.org"
    __doi__ = '10.5281/zenodo.7740139'
    __url_template__ = 'https://' + __domain__ + '/languages/{0[id]}'
    __label_template__ = '{0[name]}'


class Lexibank(LinkProvider):  # pragma: no cover  # pylint: disable=R0903,C0115
    __inactive__ = True
    __domain__ = "lexibank.clld.org"
    __doi__ = '10.5281/zenodo.5227817'
    __url_template__ = 'https://' + __domain__ + '/languages/{0[id]}'
    __label_template__ = '{0[name]}'
