import os
import re
import typing
import pathlib
import datetime
import warnings
import functools
import configparser

from clldutils.inifile import INI
from newick import Node

from .models import (
    Glottocode, Country, Reference, Endangerment, Link,
    ClassificationComment, EthnologueComment, ISORetirement,
)
from pyglottolog import config

__all__ = ['Languoid']

INFO_FILENAME = 'md.ini'

ISO_8601_INTERVAL = re.compile(
    r'(?P<start_sign>[+-]?)'
    r'(?P<start_date>\d{1,4}-\d{2}-\d{2})'
    r'/'
    r'(?P<end_sign>[+-]?)'
    r'(?P<end_date>\d{1,4}-\d{2}-\d{2})',
    flags=re.ASCII)


@functools.total_ordering
class Languoid(object):
    """
    Info on languoids is encoded in the INI files and in the directory hierarchy of
    :attr:`pyglottolog.Glottolog.tree`.
    This class provides access to all of it.

    **Languoid formatting**:

    :ivar _format_specs: A `dict` mapping custom format specifiers to conversion functions. Usage:

    .. code-block:: python

        >>> l = Languoid.from_name_id_level(pathlib.Path('.'), 'N(a,m)e', 'abcd1234', 'language')
        >>> '{0:newick_name}'.format(l)
        'N{a/m}e'

    .. seealso::

        `<https://www.python.org/dev/peps/pep-3101/#format-specifiers>`_ and
        `<https://www.python.org/dev/peps/pep-3101/#controlling-formatting-on-a-per-type-basis>`_
    """
    section_core = 'core'

    def __init__(
            self,
            cfg: INI,
            lineage: typing.Union[None, typing.List[typing.Tuple[str, str, str]]] = None,
            id_: typing.Union[None, str] = None,
            directory: typing.Union[None, pathlib.Path] = None,
            tree: typing.Union[None, pathlib.Path] = None,
            _api=None):
        """
        Refer to the factory methods for typical use cases of instantiating a `Languoid`:

        - :meth:`Languoid.from_dir`
        - :meth:`Languoid.from_id_name_level`

        :param cfg: `INI` instance storing the languoid's metadata.
        :param lineage: list of ancestors (from root to this languoid).
        :param id_: Glottocode for the languoid (or `None`, if `directory` is passed).
        :param _api: Some properties require access to config data which is accessed through a \
        `Glottolog` API instance.
        """
        assert (id_ and tree) or directory
        if id_ is None:
            id_ = Glottocode(directory.name)
        lineage = lineage or []
        assert all(Glottocode.pattern.match(id) for _, id, _ in lineage)
        self.lineage = [
            (name, id, _api.languoid_levels.get(level) if _api else level)
            for name, id, level in lineage]
        self.cfg = cfg
        self.dir = directory or tree.joinpath(*[id for name, id, _ in self.lineage])
        self._id = id_
        self._api = _api

    @classmethod
    def from_dir(cls, directory: pathlib.Path, nodes=None, _api=None, **kw):
        """
        Create a `Languoid` from a directory, named with the Glottocode and containing `md.ini`.

        This method is used by :class:`pyglottolog.Glottolog` to read `Languoid`s from the
        repository's `languoids/tree` directory.
        """
        if _api and _api.cache and directory.name in _api.cache:
            return _api.cache[directory.name]

        if nodes is None:
            nodes = {}
        cfg = INI.from_file(directory.joinpath(INFO_FILENAME), interpolation=None)

        lineage = []
        for parent in directory.parents:
            id_ = parent.name
            assert id_ != directory.name
            if not Glottocode.pattern.match(id_):
                # we ignore leading non-languoid-dir path components.
                break

            if id_ not in nodes:
                l_ = Languoid.from_dir(parent, nodes=nodes, _api=_api, **kw)
                nodes[id_] = (l_.name, l_.id, l_.level)
            lineage.append(nodes[id_])

        res = cls(cfg, list(reversed(lineage)), directory=directory, _api=_api, **kw)
        nodes[res.id] = (res.name, res.id, res.level)
        return res

    @classmethod
    def from_name_id_level(cls, tree, name, id, level, **kw):
        """
        This method is used in `pyglottolog.lff` to instantiate `Languoid` s for new nodes
        encountered in "lff"-format trees.
        """
        cfg = INI(interpolation=None)
        cfg.read_dict(dict(core=dict(name=name)))
        res = cls(cfg, kw.pop('lineage', []), id_=Glottocode(id), tree=tree)
        for k, v in kw.items():
            setattr(res, k, v)
        # Note: Setting the level behaves differently when `_api` is available, so must be done
        # after all other attributes are initialized.
        res.level = level
        return res

    # We provide a couple of node label format specifications which can be used when serializing
    # trees in newick format.
    _format_specs = {
        'newick_name': (
            lambda l: l.name.replace(
                ',', '/').replace('(', '{').replace(')', '}').replace("'", "''"),
            "Languoid name with special newick characters replaced"),
        'newick_level': (
            lambda l: '-l-' if getattr(l.level, 'id', l.level) == 'language' else '',
            "Languoid level in case of languages"),
        'newick_iso': (
            lambda l: '[{0}]'.format(l.iso) if l.iso else '',
            "Bracketed ISO code or nothing"),
    }
    _newick_default_template = "'{l:newick_name} [{l.id}]{l:newick_iso}{l:newick_level}'"

    def __format__(self, format_spec):
        if format_spec in self._format_specs:
            return self._format_specs[format_spec][0](self)
        return object.__format__(self, format_spec)

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self.id == other.id

    def __lt__(self, other):
        """
        To allow Languoid lists to be sorted, we implement a simple ordering by Glottocode.
        """
        return self.id < other.id

    def __repr__(self):
        return '<%s %s>' % (getattr(self.level, 'name', self.level).capitalize(), self.id)

    def __str__(self):
        return '%s [%s]' % (self.name, self.id)

    def _set(self, key, value, section=None):
        section = section or self.section_core
        if value is None and key in self.cfg[section]:
            del self.cfg[section][key]
        else:
            self.cfg.set(section, key, value)

    def _get(self, key, type_=None):
        res = self.cfg.get(self.section_core, key, fallback=None)
        if type_ and res:
            return type_(res)
        return res

    def newick_node(self, nodes=None, template=None, maxlevel=None, level=0) -> Node:
        """
        Return a `newick.Node` representing the subtree of the Glottolog classification starting
        at the languoid.

        :param template: Python format string accepting the `Languoid` instance as single \
        variable named `l`, used to format node labels.
        """
        template = template or self._newick_default_template
        n = Node(name=template.format(l=self), length='1')  # noqa: E741

        children = self.children if nodes is None else self.children_from_nodemap(nodes)
        for nn in sorted(children, key=lambda nn: nn.name):
            if maxlevel:
                if (isinstance(maxlevel, config.LanguoidLevel) and nn.level > maxlevel) or \
                        (not isinstance(maxlevel, config.LanguoidLevel) and level > maxlevel):
                    continue
            n.add_descendant(
                nn.newick_node(nodes=nodes, template=template, maxlevel=maxlevel, level=level + 1))
        return n

    def write_info(self, outdir: typing.Union[None, pathlib.Path] = None):
        """
        Write `Languoid` metadata as INI file to `outdir/<INFO_FILENAME>`.
        """
        outdir = outdir or self.dir
        if not isinstance(outdir, pathlib.Path):
            outdir = pathlib.Path(outdir)
        if outdir.name != self.id:
            outdir = outdir.joinpath(self.id)
        if not outdir.exists():
            outdir.mkdir()
        fname = outdir.joinpath(INFO_FILENAME)
        self.cfg.write(fname)
        if os.linesep == '\n':
            with fname.open(encoding='utf8') as fp:
                text = fp.read()
            with fname.open('w', encoding='utf8') as fp:
                fp.write(text.replace('\n', '\r\n'))
        return fname

    # -------------------------------------------------------------------------
    # Accessing info of a languoid
    # -------------------------------------------------------------------------
    @property
    def glottocode(self):
        """Alias for `id`"""
        return self._id

    @property
    def id(self):
        return self._id

    @property
    def category(self):
        """
        Languoid category.

        - Category name from :class:`pyglottolog.config.LanguageType` for languoids of level \
          "language",
        - `"Family"` or `"Pseudo Family"` for families,
        - `"Dialect"` for dialects.
        """
        # Computing the category requires access to config data:
        if self._api:
            pseudo_families = {
                c.pseudo_family_id: c.category for c in self._api.language_types.values()}
            fid = self.lineage[0][1] if self.lineage else None
            if self.level == self._api.languoid_levels.language:
                return pseudo_families.get(fid, self._api.language_types['spoken_l1'].category)
            cat = self.level.name.capitalize()
            if self.level == self._api.languoid_levels.family:
                if self.id.startswith('unun9') or \
                        self.id in pseudo_families or fid in pseudo_families:
                    cat = 'Pseudo ' + cat
            return cat

    @property
    def isolate(self) -> bool:
        """
        Flag signaling whether the languoid is an isolate, i.e. has level "language" and is not
        member of a family.
        """
        return getattr(self.level, 'id', self.level) == 'language' and not self.lineage

    def children_from_nodemap(self, nodes):
        # A faster alternative to `children` when the relevant languoids have already been
        # read from disc.
        return [nodes[d.name] for d in self.dir.iterdir() if d.is_dir()]

    def descendants_from_nodemap(self, nodes, level=None):
        if isinstance(level, str):
            level = self._api.languoid_levels.get(level)
        return [
            n for n in nodes.values() if
            n.lineage and self.id in [li[1] for li in n.lineage] and  # noqa: W504
            ((level is None) or n.level == level)]

    @property
    def children(self) -> typing.List['Languoid']:
        """
        List of direct descendants of the languoid in the classification tree.

        .. note::

            Using this on many languoids can be slow, because the directory tree may be traversed
            and INI files read multiple times. To circumvent this problem, you may use a read-only
            :class:`pyglottolog.Glottolog` instance, by passing `cache=True` at initialization.
        """
        return [Languoid.from_dir(d, _api=self._api) for d in self.dir.iterdir() if d.is_dir()]

    def ancestors_from_nodemap(self, nodes):
        # A faster alternative to `ancestors` when the relevant languoids have already
        # been read from disc.
        return [nodes[lineage[1]] for lineage in self.lineage]

    def iter_ancestors(self):
        for parent in self.dir.parents:
            id_ = parent.name
            if Glottocode.pattern.match(id_):
                yield Languoid.from_dir(parent, _api=self._api)
            else:
                # we ignore leading non-languoid-dir path components.
                break

    def iter_descendants(self):
        for child in self.children:
            yield child
            yield from child.iter_descendants()

    @property
    def ancestors(self) -> typing.List['Languoid']:
        """
        List of ancestors of the languoid in the classification tree, from root (i.e. top-level
        family) to parent node.

        .. note::

            Using this on many languoids can be slow, because the directory tree may be traversed
            and INI files read multiple times. To circumvent this problem, you may use a read-only
            :class:`pyglottolog.Glottolog` instance, by passing `cache=True` at initialization.
        """
        return list(reversed(list(self.iter_ancestors())))

    @property
    def parent(self) -> typing.Union['Languoid', None]:
        """
        Parent languoid or `None`.

        .. note::

            Using this on many languoids can be slow, because the directory tree may be traversed
            and INI files read multiple times. To circumvent this problem, you may use a read-only
            :class:`pyglottolog.Glottolog` instance, by passing `cache=True` at initialization.
        """
        try:
            return next(self.iter_ancestors())
        except StopIteration:
            return

    @property
    def family(self) -> typing.Union['Languoid', None]:
        """
        Top-level family the languoid belongs to or `None`.

        .. note::

            Using this on many languoids can be slow, because the directory tree may be traversed
            and INI files read multiple times. To circumvent this problem, you may use a read-only
            :class:`pyglottolog.Glottolog` instance, by passing `cache=True` at initialization.
        """
        return self.ancestors[0] if self.lineage else None

    @property
    def names(self) -> typing.Dict[str, list]:
        """
        A `dict` mapping alternative name providers to `list` s of alternative names for the
        languoid by the given provider.
        """
        if 'altnames' in self.cfg:
            return {k: self.cfg.getlist('altnames', k) for k in self.cfg['altnames']}
        return {}

    def add_name(self, name, type_='glottolog'):
        names = self.cfg.getlist('altnames', type_)
        if name not in names:
            self.cfg.set('altnames', type_, sorted(names + [name]))

    def update_names(self, names, type_='glottolog'):
        new = set(names)
        if new != set(self.cfg.getlist('altnames', type_)):
            self.cfg.set('altnames', type_, sorted(new))
            return True
        return False

    @property
    def identifier(self) -> typing.Union[dict, configparser.SectionProxy]:
        if 'identifier' in self.cfg:
            return self.cfg['identifier']
        return {}

    @property
    def sources(self) -> typing.List[Reference]:
        """
        List of Glottolog references linked to the languoid

        :rtype: :class:`pyglottolog.references.Reference`
        """
        if self.cfg.has_option('sources', 'glottolog'):
            return Reference.from_list(self.cfg.getlist('sources', 'glottolog'))
        return []

    @sources.setter
    def sources(self, refs):
        assert all(isinstance(r, Reference) for r in refs)
        self.cfg.set('sources', 'glottolog', ['{0}'.format(ref) for ref in refs])

    @property
    def endangerment(self) -> typing.Union[None, Endangerment]:
        """
        Endangerment information about the languoid.

        :rtype: :class:`Endangerment`
        """
        if ('endangerment' in self.cfg) and self._api:
            kw = {k: v for k, v in self.cfg['endangerment'].items()}
            kw['status'] = self._api.aes_status.get(kw['status'])
            if kw['source'] in self._api.aes_sources:
                kw['source'] = self._api.aes_sources[kw['source']]
            else:
                ref = Reference.from_string(kw['source'])
                kw['source'] = config.AESSource(
                    id=ref.key,
                    name=None,
                    url=None,
                    reference_id=ref.key,
                    pages=ref.pages)
            return Endangerment(**kw)

    @property
    def classification_comment(self) -> typing.Union[None, ClassificationComment]:
        """
        Classification information about the languoid.

        :rtype: :class:`ClassificationComment`
        """
        if 'classification' in self.cfg:
            cfg = self.cfg['classification']
            return ClassificationComment(
                family=cfg.get('family'),
                familyrefs=self.cfg.getlist('classification', 'familyrefs'),
                sub=cfg.get('sub'),
                subrefs=self.cfg.getlist('classification', 'subrefs'))

    @property
    def ethnologue_comment(self) -> typing.Union[None, EthnologueComment]:
        """
        Commentary about the classification of the languoid in Ethnologue.

        :rtype: :class:`EthnologueComment`
        """
        section = 'hh_ethnologue_comment'
        if section in self.cfg:
            return EthnologueComment(**self.cfg[section])

    @property
    def macroareas(self) -> typing.List[config.Macroarea]:
        """
        :rtype: `list` of :class:`config.Macroarea`
        """
        if self._api:
            return [
                self._api.macroareas.get(n)
                for n in self.cfg.getlist(self.section_core, 'macroareas')]
        return []

    @macroareas.setter
    def macroareas(self, value):
        if self._api:
            assert isinstance(value, (list, tuple)) \
                and all(self._api.macroareas.get(n) for n in value)
            self._set('macroareas', [ma.name for ma in value])

    @property
    def timespan(self, _date_format='%Y-%m-%d'):
        value = self.cfg.get(self.section_core, 'timespan',
                             fallback=None)
        if not value:
            return None
        value = value.strip()
        ma = ISO_8601_INTERVAL.fullmatch(value)
        if ma is None:
            raise ValueError('invalid interval', value)  # pragma: no cover

        dates = ma.group('start_date', 'end_date')

        def fix_date(d, year_tmpl='{:04d}'):
            year, sep, rest = d.partition('-')
            assert year and sep and rest
            year = year_tmpl.format(int(year))
            return '{}{}{}'.format(year, sep, rest)

        dates = map(fix_date, dates)
        dates = [datetime.datetime.strptime(d, _date_format).date() for d in dates]

        if any((d.month, d.day) != (1, 1) for d in dates):  # pragma: no cover
            warnings.warn('ignoring non -1-1 date(s) month/day: {!r}'.format(dates))

        start, end = dates
        return (
            -start.year if ma.group('start_sign') == '-' else start.year,
            -end.year if ma.group('end_sign') == '-' else end.year)

    @timespan.setter
    def timespan(self, value):
        if not (isinstance(value, (list, tuple)) and len(value) == 2):
            raise ValueError(value)

        # https://en.wikipedia.org/wiki/ISO_8601#Years
        if not all(-9999 <= v <= 9999 for v in value):
            warnings.warn('serializing year(s) outside the four-digit-range: {!r}'.format(value))

        def fmt(v):
            sign = '-' if v < 0 else ''
            return '{}{:04d}'.format(sign, abs(v))

        self._set('timespan', '{}-01-01/{}-01-01'.format(*map(fmt, value)))

    @property
    def links(self) -> typing.List[Link]:
        """
        Links to web resources related to the languoid
        """
        return [Link.from_string(s) for s in self.cfg.getlist(self.section_core, 'links')]

    @links.setter
    def links(self, value):
        assert isinstance(value, list)
        self._set('links', [v.to_string() for v in sorted(Link.from_(v) for v in value)])

    def update_links(self, domain, urls):
        new = [li for li in self.links if li.domain != domain] + [Link.from_(u) for u in urls]
        if set(new) != set(self.links):
            self.links = new
            return True
        return False

    @property
    def countries(self) -> typing.List[Country]:
        """
        Countries a language is spoken in.
        """
        return [Country.from_text(n)
                for n in self.cfg.getlist(self.section_core, 'countries')]

    @countries.setter
    def countries(self, value):
        assert isinstance(value, (list, tuple)) \
            and all(isinstance(o, Country) for o in value)
        self._set('countries', ['{0}'.format(c) for c in value])

    @property
    def name(self):
        """
        The Glottolog mame of the languoid
        """
        return self._get('name')

    @name.setter
    def name(self, value):
        self._set('name', value)

    @property
    def latitude(self) -> typing.Union[None, float]:
        """
        The geographic latitude of the point chosen as representative coordinate of the languoid
        """
        return self._get('latitude', float)

    @latitude.setter
    def latitude(self, value):
        self._set('latitude', round(float(value), 5))

    @property
    def longitude(self) -> typing.Union[None, float]:
        """
        The geographic longitude of the point chosen as representative coordinate of the languoid
        """
        return self._get('longitude', float)

    @longitude.setter
    def longitude(self, value):
        self._set('longitude', round(float(value), 5))

    @property
    def hid(self):
        return self._get('hid')

    @hid.setter
    def hid(self, value):
        self._set('hid', value)

    @property
    def level(self):
        if self._api:
            return self._get('level', self._api.languoid_levels.get)
        return self._get('level', lambda s: s)

    @level.setter
    def level(self, value):
        if self._api:
            self._set('level', self._api.languoid_levels.get(value).id)

    @property
    def iso(self):
        return self._get('iso639-3')

    @iso.setter
    def iso(self, value):
        self._set('iso639-3', value)

    @property
    def iso_code(self):
        return self._get('iso639-3')

    @iso_code.setter
    def iso_code(self, value):
        self._set('iso639-3', value)

    @property
    def iso_retirement(self):
        if 'iso_retirement' in self.cfg:
            kw = dict(self.cfg['iso_retirement'])
            if 'change_to' in kw:
                kw['change_to'] = self.cfg.getlist('iso_retirement', 'change_to')
            if 'comment' in kw:
                kw['comment'] = self.cfg.gettext('iso_retirement', 'comment')
            return ISORetirement(**kw)

    @property
    def fname(self):
        return self.dir.joinpath(INFO_FILENAME)
