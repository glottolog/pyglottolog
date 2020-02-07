import re
import os
import pathlib
import contextlib
import collections

import pycldf.util
from csvw import TableGroup, Column
from clldutils.path import walk, git_describe
from clldutils.misc import lazyproperty
from clldutils.apilib import API
from clldutils.jsonlib import load
import pycountry
from termcolor import colored
from tqdm import tqdm

from . import util
from . import languoids
from . import references
from . import config
from .languoids import models

__all__ = ['Glottolog']

ISO_CODE_PATTERN = re.compile('[a-z]{3}$')


class Glottolog(API):
    """API to access Glottolog data"""
    countries = [models.Country(c.alpha_2, c.name) for c in pycountry.countries]
    __config__ = {
        'aes_status': config.AES,
        'aes_sources': config.AESSource,
        'document_types': config.DocumentType,
        'med_types': config.MEDType,
        'macroareas': config.Macroarea,
        'language_types': config.LanguageType,
        'languoid_levels': config.LanguoidLevel,
        'editors': config.Generic,
        'publication': config.Generic,
    }

    def __init__(self, repos='.'):
        API.__init__(self, repos=repos)
        self.repos = self.repos.resolve()
        self.tree = self.repos / 'languoids' / 'tree'
        if not self.tree.exists():
            raise ValueError('repos dir %s missing tree dir: %s' % (self.repos, self.tree))
        if not self.repos.joinpath('references').exists():
            raise ValueError('repos dir %s missing references subdir' % (self.repos,))
        for name, cls in self.__config__.items():
            fname = self.repos / 'config' / (name + '.ini')
            setattr(self, name, config.Config.from_ini(fname, object_class=cls))

    def __str__(self):
        return '<Glottolog repos {0} at {1}>'.format(git_describe(self.repos), self.repos)

    def describe(self):
        return git_describe(self.repos)

    def build_path(self, *comps):
        build_dir = self.repos.joinpath('build')
        if not build_dir.exists():
            build_dir.mkdir()  # pragma: no cover
        return build_dir.joinpath(*comps)

    @contextlib.contextmanager
    def cache_dir(self, name):
        d = self.build_path(name)
        if not d.exists():
            d.mkdir()
        yield d

    def references_path(self, *comps):
        return self.repos.joinpath('references', *comps)

    def languoids_path(self, *comps):
        return self.repos.joinpath('languoids', *comps)

    @lazyproperty
    def iso(self):
        """
        :return: `clldutils.iso_639_3.ISO` instance, fed with the data of the latest
        ISO code table zip found in the build directory.
        """
        return util.get_iso(self.build_path())

    @property
    def glottocodes(self):
        return models.Glottocodes(self.languoids_path('glottocodes.json'))

    @property
    def ftsindex(self):
        return self.build_path('whoosh')

    def languoid(self, id_):
        if isinstance(id_, languoids.Languoid):
            return id_

        if ISO_CODE_PATTERN.match(id_):
            for d in walk(self.tree, mode='dirs'):
                l_ = languoids.Languoid.from_dir(d, _api=self)
                if l_.iso_code == id_:
                    return l_
        else:
            for d in walk(self.tree, mode='dirs'):
                if d.name == id_:
                    return languoids.Languoid.from_dir(d, _api=self)

    def languoids(self, ids=None, maxlevel=None, exclude_pseudo_families=False):
        """
        :param ids:
        :param maxlevel: Numeric maximal nesting depth of languoids, or Languoid.level.
        :return: Generator object, to iterate over languoids.
        """
        if isinstance(maxlevel, int):
            pass
        else:
            maxlevel = self.languoid_levels.get(maxlevel or 'dialect')
        nodes = {}

        for dirpath, dirnames, filenames in os.walk(str(self.tree)):
            dp = pathlib.Path(dirpath)
            if dp.name in nodes \
                    and (not isinstance(maxlevel, int)) \
                    and nodes[dp.name][2] > maxlevel:
                del dirnames[:]

            for dirname in dirnames:
                if ids is None or dirname in ids:
                    lang = languoids.Languoid.from_dir(dp.joinpath(dirname), nodes=nodes, _api=self)
                    if (isinstance(maxlevel, int) and len(lang.lineage) <= maxlevel) \
                            or ((not isinstance(maxlevel, int)) and lang.level <= maxlevel):
                        if (not exclude_pseudo_families) or not lang.category.startswith('Pseudo'):
                            yield lang

    def languoids_by_code(self, nodes=None):
        """
        Returns a `dict` mapping the three major language code schemes
        (Glottocode, ISO code, and Harald's NOCODE_s) to Languoid objects.
        """
        res = {}
        for lang in (self.languoids() if nodes is None else nodes.values()):
            res[lang.id] = lang
            if lang.hid:
                res[lang.hid] = lang
            if lang.iso:
                res[lang.iso] = lang
        return res

    def ascii_tree(self, start, maxlevel=None):
        _ascii_node(
            self.languoid(start),
            0,
            True,
            self.languoid_levels.get(maxlevel, maxlevel) if maxlevel else None,
            '',
            self.languoid_levels)

    def newick_tree(self, start=None, template=None, nodes=None, maxlevel=None):
        template = template or languoids.Languoid._newick_default_template
        if start:
            return self.languoid(start).newick_node(
                template=template, nodes=nodes, maxlevel=maxlevel, level=1).newick + ';'
        if nodes is None:
            nodes = collections.OrderedDict((l.id, l) for l in self.languoids())
        trees = []
        for lang in nodes.values():
            if not lang.lineage and not lang.category.startswith('Pseudo '):
                ns = lang.newick_node(
                    nodes=nodes, template=template, maxlevel=maxlevel, level=1).newick
                if lang.level == self.languoid_levels.language:
                    # An isolate: we wrap it in a pseudo-family with the same name and ID.
                    fam = languoids.Languoid.from_name_id_level(
                        lang.dir.parent, lang.name, lang.id, 'family', _api=self)
                    ns = '({0}){1}:1'.format(ns, template.format(l=fam))  # noqa: E741
                trees.append('{0};'.format(ns))
        return '\n'.join(trees)

    @lazyproperty
    def bibfiles(self):
        return references.BibFiles.from_path(self.references_path(), api=self)

    def refs_by_languoid(self, nodes=None):
        all = {}
        languoids_by_code = self.languoids_by_code(nodes or {l.id: l for l in self.languoids()})
        res = collections.defaultdict(list)
        for bib in tqdm(self.bibfiles):
            for entry in bib.iterentries():
                all[entry.id] = entry
                for lang in entry.languoids(languoids_by_code)[0]:
                    res[lang.id].append(entry)
        return res, all

    @lazyproperty
    def hhtypes(self):
        return references.HHTypes(self.references_path('hhtype.ini'))

    @lazyproperty
    def triggers(self):
        res = {'inlg': [], 'lgcode': []}
        for lang in self.languoids():
            for type_ in res:
                if lang.cfg.has_option('triggers', type_):
                    label = '%s [%s]' % (lang.name, lang.hid or lang.id)
                    res[type_].extend([util.Trigger(type_, label, text)
                                       for text in lang.cfg.getlist('triggers', type_)])
        return res

    @lazyproperty
    def macroarea_map(self):
        res = {}
        for lang in self.languoids():
            ma = lang.macroareas[0].name if lang.macroareas else ''
            res[lang.id] = ma
            if lang.iso:
                res[lang.iso] = ma
            if lang.hid:
                res[lang.hid] = ma
        return res

    @property
    def current_editors(self):
        return sorted([e for e in self.editors.values() if e.current], key=lambda e: int(e.ord))

    def write_languoids_table(self, outdir, version=None):
        version = version or self.describe()
        out = outdir / 'glottolog-languoids-{0}.csv'.format(version)
        md = outdir / (out.name + '-metadata.json')
        tg = TableGroup.fromvalue({
            "@context": "http://www.w3.org/ns/csvw",
            "dc:version": version,
            "dc:bibliographicCitation":
                "{0}. "
                "{1} [Data set]. "
                "Zenodo. https://doi.org/{2}".format(
                    ' & '.join([e.name for e in self.current_editors]),
                    self.publication.zenodo.title_format.format('(Version {0})'.format(version)),
                    self.publication.zenodo.doi,
                ),
            "tables": [load(pycldf.util.pkg_path('components', 'LanguageTable-metadata.json'))],
        })
        tg.tables[0].url = out.name
        for col in [
            dict(name='LL_Code'),
            dict(name='Classification', separator='/'),
            dict(name='Family_Glottocode'),
            dict(name='Family_Name'),
            dict(name='Language_Glottocode'),
            dict(name='Language_Name'),
            dict(name='Level', datatype=dict(base='string', format='family|language|dialect')),
            dict(name='Status'),
        ]:
            tg.tables[0].tableSchema.columns.append(Column.fromvalue(col))

        langs = []
        for lang in self.languoids():
            lid, lname = None, None
            if lang.level == self.languoid_levels.language:
                lid, lname = lang.id, lang.name
            elif lang.level == self.languoid_levels.dialect:
                for lname, lid, level in reversed(lang.lineage):
                    if level == self.languoid_levels.language:
                        break
                else:  # pragma: no cover
                    raise ValueError
            langs.append(dict(
                ID=lang.id,
                Name=lang.name,
                Macroarea=lang.macroareas[0].name if lang.macroareas else None,
                Latitude=lang.latitude,
                Longitude=lang.longitude,
                Glottocode=lang.id,
                ISO639P3code=lang.iso,
                LL_Code=lang.identifier.get('multitree'),
                Classification=[c[1] for c in lang.lineage],
                Language_Glottocode=lid,
                Language_Name=lname,
                Family_Name=lang.lineage[0][0] if lang.lineage else None,
                Family_Glottocode=lang.lineage[0][1] if lang.lineage else None,
                Level=lang.level.name,
                Status=lang.endangerment.status.name if lang.endangerment else None,
            ))

        tg.to_file(md)
        tg.tables[0].write(langs, fname=out)
        return md, out


def _ascii_node(n, level, last, maxlevel, prefix, levels):
    nlevel = levels.get(n.level)
    if maxlevel:
        if (isinstance(maxlevel, config.LanguoidLevel) and nlevel > maxlevel) or \
                (not isinstance(maxlevel, config.LanguoidLevel) and level > maxlevel):
            return
    s = '\u2514' if last else '\u251c'
    s += '\u2500 '

    if not level:
        for i, node in enumerate(n.ancestors):
            util.sprint('{0}{1}{2} [{3}]', prefix, s if i else '', node.name, node.id)
            prefix = '   ' + prefix

    nprefix = prefix + ('   ' if last else '\u2502  ')

    color = 'red' if not level else (
        'green' if nlevel == levels.language else (
            'blue' if nlevel == levels.dialect else None))

    util.sprint(
        '{0}{1}{2} [{3}]',
        prefix,
        s if level else (s if n.ancestors else ''),
        colored(n.name, color) if color else n.name,
        colored(n.id, color) if color else n.id)
    for i, c in enumerate(sorted(n.children, key=lambda nn: nn.name)):
        _ascii_node(c, level + 1, i == len(n.children) - 1, maxlevel, nprefix, levels)
