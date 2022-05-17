"""Load references from .bib files into sqlite3, hash, assign ids (split/merge)."""

import collections
import contextlib
import difflib
import functools
import itertools
import logging
import operator
import pathlib
import typing

from clldutils import jsonlib
from csvw import dsv
import sqlalchemy as sa
import sqlalchemy.orm

from .. import _compat
from ..util import (unique,
                    group_first as groupby_first)
from . import bibtex

__all__ = ['Database']

UNION_FIELDS = {'fn', 'asjp_name', 'isbn'}

IGNORE_FIELDS = {'crossref', 'numnote', 'glotto_id'}

REF_ID_FIELD = 'glottolog_ref_id'

ENCODING = 'utf-8'

SQLALCHEMY_FUTURE = True

PAGE_SIZE = 32_768

ENTRYTYPE = 'ENTRYTYPE'


log = logging.getLogger('pyglottolog')


def distance(left, right,
             *, weight={'author': 3, 'year': 3, 'title': 3, ENTRYTYPE: 2}):
    """Simple measure of the difference between two BibTeX field dicts."""
    if not (left or right):
        return 0.0

    keys = left.keys() & right.keys()
    if not keys:
        return 1.0

    weights = {k: weight.get(k, 1) for k in keys}
    ratios = (w * difflib.SequenceMatcher(None, left[k], right[k]).ratio()
              for k, w in weights.items())
    return 1 - (sum(ratios) / sum(weights.values()))


registry = sa.orm.registry()


class Connectable:
    """SQLite database."""

    def __init__(self, filepath,
                 *, future: bool = SQLALCHEMY_FUTURE,
                 paramstyle: typing.Optional[str] = 'qmark'):
        self.filepath = pathlib.Path(filepath)
        self._engine = sa.create_engine(f'sqlite:///{self.filepath}',
                                        future=future,
                                        paramstyle=paramstyle)

    def connect(self,
                *, pragma_bulk_insert: bool = False,
                page_size: typing.Optional[int] = None):
        """Connect to engine, optionally apply SQLite PRAGMAs, return conn."""
        conn = self._engine.connect()

        if page_size is not None:
            conn.execute(sa.text(f'PRAGMA page_size = {page_size:d}'))

        if pragma_bulk_insert:
            conn.execute(sa.text('PRAGMA synchronous = OFF'))
            conn.execute(sa.text('PRAGMA journal_mode = MEMORY'))

        return conn

    @contextlib.contextmanager
    def execute(self, statement, *, closing: bool = True):
        """Connect to engine, execute ``statement``, return ``CursorResult``, close."""
        with self.connect() as conn:
            result = conn.execute(statement)
            manager = contextlib.closing if closing else contextlib.nullcontext
            with manager(result) as result:
                yield result


class BaseDatabase(Connectable):
    """Collection of parsed .bib files loaded into a SQLite database."""

    @classmethod
    def from_bibfiles(cls, bibfiles, filepath, *, rebuild: bool = False,
                      page_size: typing.Optional[int] = PAGE_SIZE,
                      verbose: bool = False):
        """Load ``bibfiles`` if needed, hash, split/merge, return the database."""
        self = cls(filepath)
        if self.filepath.exists():
            if not rebuild and self.is_uptodate(bibfiles):
                return self
            self.filepath.unlink()

        with self.connect(page_size=page_size) as conn:
            registry.metadata.create_all(conn)
            conn.commit()

        with self.connect(pragma_bulk_insert=True) as conn:
            import_bibfiles(conn, bibfiles)
            conn.commit()

            Entry.stats(conn=conn)
            Value.fieldstats(conn=conn)

            generate_hashes(conn)
            conn.commit()

            Entry.hashstats(conn=conn)
            Entry.hashidstats(conn=conn)

            assign_ids(conn, verbose=verbose)
            conn.commit()

        return self

    def is_uptodate(self, bibfiles, *, verbose: bool = False):
        """Does the db have the same filenames, sizes, and mtimes as ``bibfiles``?"""
        with self.connect() as conn:
            return File.same_as(conn, bibfiles, verbose=verbose)

    def __iter__(self, *, chunksize: int = 100):
        """Yield pairs of ``(Entry.id, Entry.hash)`` and unmerged field values."""
        with self.connect() as conn:
            assert Entry.allid(conn=conn)
            assert Entry.onetoone(conn=conn)

        select_values = (sa.select(Entry.id,
                                   Entry.hash,
                                   Value.field,
                                   Value.value,
                                   File.name.label('filename'),
                                   Entry.bibkey)
                         .join_from(Entry, File).join(Value)
                         .where(sa.between(Entry.id, sa.bindparam('first'), sa.bindparam('last')))
                         .order_by('id',
                                   'field',
                                   File.priority.desc(),
                                   'filename', 'bibkey'))

        groupby_id_hash = functools.partial(itertools.groupby,
                                            key=operator.attrgetter('id', 'hash'))

        groupby_field = functools.partial(itertools.groupby,
                                          key=operator.attrgetter('field'))

        with self.connect() as conn:
            for first, last in Entry.windowed(conn, key_column='id', size=chunksize):
                result = conn.execute(select_values, {'first': first, 'last': last})
                for id_hash, grp in groupby_id_hash(result):
                    fields = [(field, [(r.value, r.filename, r.bibkey) for r in g])
                              for field, g in groupby_field(grp)]
                    yield id_hash, fields

    def merged(self, *, ref_id_field: str = REF_ID_FIELD):
        """Yield ``(bibkey, (entrytype, fields))`` entries merged by ``Entry.id``."""
        for (id_, hash_), grp in self:
            entrytype, fields = self._merged_entry(grp)
            fields[ref_id_field] = f'{id_:d}'
            yield hash_, (entrytype, fields)

    @staticmethod
    def _merged_entry(grp,
                      *, union=UNION_FIELDS, ignore=IGNORE_FIELDS,
                      raw: bool = False,
                      _sep_join=', '.join,
                      _removesuffix=_compat.removesuffix):
        # TODO: consider implementing (a subset of?) onlyifnot logic:
        # {'address': 'publisher', 'lgfamily': 'lgcode', 'publisher': 'school',
        # 'journal': 'booktitle'}
        fields = {field: values[0][0] if field not in union
                  else _sep_join(unique(vl for vl, _, _ in values))
                  for field, values in grp if field not in ignore}

        src = {_removesuffix(filename, '.bib')
               for _, values in grp
               for _, filename, _ in values}

        srctrickle = {f"{_removesuffix(filename, '.bib')}#{bibkey}"
                      for _, values in grp
                      for _, filename, bibkey in values}

        fields.update(src=_sep_join(sorted(src)),
                      srctrickle=_sep_join(sorted(srctrickle)))

        if raw:
            return fields
        entrytype = fields.pop(ENTRYTYPE)
        return entrytype, fields


class Indexable:
    """Retrieve entry from individual .bib file, or merged entry from old or new grouping."""

    def __getitem__(self, key: typing.Union[typing.Tuple[str, str], int, str]):
        """
        Entry by ``(filename, bibkey)`` or merged entry by ``refid`` (old grouping)
        or ``hash`` (current grouping).
        """
        if not isinstance(key, (tuple, int, str)):
            raise TypeError(f'key must be tuple, int, or str: {key!r}')  # pragma: no cover

        with self.connect() as conn:
            if isinstance(key, tuple):
                filename, bibkey = key
                entry = self._get_file_entry(conn, filename, bibkey)
            else:
                entry = self._get_merged_entry(conn, key=key, raw=False)

        entrytype, fields = entry
        return key, (entrytype, fields)

    @staticmethod
    def _get_file_entry(conn, filename: str, bibkey: str):
        """Return entry from individual .bib file."""
        select_items = (sa.select(Value.field,
                                  Value.value)
                        .join_from(Value, Entry)
                        .filter_by(bibkey=bibkey)
                        .join(File)
                        .filter_by(name=filename))

        result = conn.execute(select_items)
        fields = dict(iter(result))

        if not fields:
            raise KeyError((filename, bibkey))
        return fields.pop(ENTRYTYPE), fields

    @classmethod
    def _get_merged_entry(cls, conn, *, key: typing.Union[int, str],
                          raw: bool = True,
                          _get_field=operator.attrgetter('field')):
        """Return merged entry from old or new grouping."""
        keycol = Entry.refid if isinstance(key, int) else Entry.hash
        select_values = (sa.select(Value.field,
                                   Value.value,
                                   File.name.label('filename'),
                                   Entry.bibkey)
                         .join_from(Entry, File).join(Value)
                         .where(keycol == key)
                         .order_by('field',
                                   File.priority.desc(),
                                   'filename', 'bibkey'))

        result = conn.execute(select_values)
        grouped = itertools.groupby(result, key=_get_field)
        grp = [(field, [(r.value, r.filename, r.bibkey) for r in g])
               for field, g in grouped]

        if not grp:
            raise KeyError(key)
        return cls._merged_entry(grp, raw=raw)


class Exportable:
    """Write merged references into .bib file, ``bibfiles``, etc."""

    def to_bibfile(self, filepath,
                   *, encoding: str = ENCODING,
                   _sortkey: typing.Optional[str] = None):
        """Write merged references into combined .bib file at ``filepath``."""
        bibtex.save(self.merged(), str(filepath),
                    sortkey=_sortkey, encoding=encoding)

    def to_csvfile(self, filename,
                   *, dialect: str = 'excel',
                   encoding: str = ENCODING):
        """Write a CSV file with one row for each entry in each .bib file."""
        select_rows = (sa.select(File.name.label('filename'),
                                 Entry.bibkey,
                                 Entry.hash,
                                 sa.cast(Entry.id, sa.Text).label('id'))
                       .join_from(File, Entry)
                       .order_by(sa.func.lower(File.name),
                                 sa.func.lower(Entry.bibkey),
                                 'hash',
                                 Entry.id))

        with self.execute(select_rows) as result,\
             dsv.UnicodeWriter(filename, encoding=encoding, dialect=dialect) as writer:
            header = list(result.keys())
            writer.writerow(header)
            writer.writerows(result)

    def to_replacements(self, filename,
                        *, indent: typing.Optional[int] = 4):
        """Write a JSON file with 301s from merged ``glottolog_ref_id``s."""
        select_pairs = (sa.select(Entry.refid.label('id'),
                                  Entry.id.label('replacement'))
                        .where(Entry.id != Entry.refid)
                        .order_by('replacement'))

        with self.execute(select_pairs) as result:
            pairs = result.mappings().all()

        with jsonlib.update(filename, default=[], indent=indent) as repls:
            # RowMapping is not JSON serializable
            repls.extend(map(dict, pairs))

    def trickle(self, bibfiles, *, ref_id_field: str = REF_ID_FIELD):
        """Write new/changed ``glottolog_ref_id``s back into ``bibfiles``."""
        with self.connect() as conn:
            assert Entry.allid(conn=conn)

        if not self.is_uptodate(bibfiles, verbose=True):
            raise RuntimeError('trickle with an outdated db')  # pragma: no cover

        changed = (Entry.id != sa.func.coalesce(Entry.refid, -1))

        select_files = (sa.select(File.pk,
                                  File.name.label('filename'))
                        .where(sa.exists()
                               .where(Entry.file_pk == File.pk)
                               .where(changed))
                        .order_by('filename'))

        select_changed = (sa.select(Entry.bibkey,
                                    sa.cast(Entry.refid, sa.Text).label('refid'),
                                    sa.cast(Entry.id, sa.Text).label('id'))
                          .where(Entry.file_pk == sa.bindparam('file_pk'))
                          .where(changed)
                          .order_by(sa.func.lower(Entry.bibkey)))

        with self.connect() as conn:
            files = conn.execute(select_files).all()
            for file_pk, filename in files:
                bf = bibfiles[filename]
                entries = bf.load()
                added = changed = 0

                changed_entries = conn.execute(select_changed, {'file_pk': file_pk})
                for bibkey, refid, new in changed_entries:
                    entrytype, fields = entries[bibkey]
                    old = fields.pop(ref_id_field, None)
                    assert old == refid
                    if old is None:
                        added += 1
                    else:
                        changed += 1
                    fields[ref_id_field] = new

                print(f'{changed:d} changed {added:d} added in {bf.id}')
                bf.save(entries)


class Debugable:
    """Show details about splitted and combined references."""

    def stats(self, *, field_files: bool = False):
        with self.connect() as conn:
            Entry.stats(conn=conn)
            Value.fieldstats(conn=conn, with_files=field_files)
            Entry.hashstats(conn=conn)
            Entry.hashidstats(conn=conn)

    def show_splits(self):
        """Print details about bibitems that have been splitted."""
        other = sa.orm.aliased(Entry)

        select_entries = (sa.select(Entry.refid,
                                    Entry.hash,
                                    File.name.label('filename'),
                                    Entry.bibkey)
                          .join_from(Entry, File)
                          .where(sa.exists()
                                 .where(other.refid == Entry.refid)
                                 .where(other.hash != Entry.hash))
                          .order_by('refid', 'hash', 'filename', 'bibkey'))

        with self.connect() as conn:
            result = conn.execute(select_entries)
            for refid, group in groupby_first(result):
                self._print_group(conn, group)
                _, _, new = split_old_cand_new(conn, group, refid=refid)
                print(f'-> {new}\n')

    def show_merges(self):
        """Print details about bibitems that have been merged."""
        other = sa.orm.aliased(Entry)

        select_entries = (sa.select(Entry.hash,
                                    Entry.refid,
                                    File.name.label('filename'),
                                    Entry.bibkey)
                          .join_from(Entry, File)
                          .where(sa.exists()
                                 .where(other.hash == Entry.hash)
                                 .where(other.refid != Entry.refid))
                          .order_by('hash',
                                    Entry.refid.desc(),
                                    'filename', 'bibkey'))

        with self.connect() as conn:
            merge = functools.partial(merge_new_cand_old, conn,
                                      keyfunc=operator.attrgetter('refid'))
            result = conn.execute(select_entries)
            for hash_, group in groupby_first(result):
                self._print_group(conn, group)
                new, _, old = merge(group, hash_=hash_)
                print(f'-> {old}\n')

    def show_identified(self):
        """Print details about new bibitems that have been merged with present ones."""
        other = sa.orm.aliased(Entry)

        select_entries = (sa.select(Entry.hash,
                                    Entry.refid,
                                    File.name.label('filename'),
                                    Entry.bibkey)
                          .join_from(Entry, File)
                          .where(sa.exists()
                                 .where(other.refid == sa.null())
                                 .where(other.hash == Entry.hash))
                          .where(sa.exists()
                                 .where(other.refid != sa.null())
                                 .where(other.hash == Entry.hash))
                          .order_by('hash',
                                    Entry.refid != sa.null(),
                                    'refid', 'filename', 'bibkey'))

        self._show(select_entries)

    def show_combined(self):
        """Print details about new bibitems that have been merged with each other."""
        self._show_new(combined=True)

    def show_new(self):
        """Print details about new bibitems that have not been merged."""
        self._show_new(combined=False)

    def _show_new(self, *, combined: bool = False):
        other = sa.orm.aliased(Entry)

        whereclause = (sa.exists()
                       .where(other.refid == sa.null())
                       .where(other.hash == Entry.hash)
                       .where(other.pk != Entry.pk))

        if not combined:
            whereclause = ~whereclause

        select_entries = (sa.select(Entry.hash,
                                    File.name.label('filename'),
                                    Entry.bibkey)
                          .join_from(Entry, File)
                          .where(Entry.refid == sa.null())
                          .where(whereclause)
                          .order_by('hash', 'filename', 'bibkey'))

        self._show(select_entries)

    def _show(self, sql):
        with self.connect() as conn:
            result = conn.execute(sql)
            for _, group in groupby_first(result):
                self._print_group(conn, group)
                print()

    @staticmethod
    def _print_group(conn, group, *, out=print):
        for row in group:
            out(row)
        for row in group:
            hashfields = Value.hashfields(conn,
                                          filename=row.filename,
                                          bibkey=row.bibkey)
            out('\t%r, %r, %r, %r' % hashfields)


class Database(Debugable, Exportable, Indexable, BaseDatabase):
    """Collection of parsed .bib files loaded into a SQLite database."""


@registry.mapped
class File:
    """Filesystem metadata and priority setting of a .bib file."""

    __tablename__ = 'file'

    pk = sa.Column(sa.Integer, primary_key=True)

    name = sa.Column(sa.Text, sa.CheckConstraint("name != ''"), nullable=False,
                     unique=True)

    size = sa.Column(sa.Integer, sa.CheckConstraint('size > 0'), nullable=False)
    mtime = sa.Column(sa.DateTime, nullable=False)

    priority = sa.Column(sa.Integer, nullable=False)

    @classmethod
    def same_as(cls, conn, bibfiles, *, verbose: bool = False):
        """Return whether all sizes and mtimes are the same as in ``bibfiles``."""
        ondisk = {b.fname.name: (b.size, b.mtime) for b in bibfiles}

        select_files = (sa.select(cls.name, cls.size, cls.mtime)
                        .order_by('name'))
        result = conn.execute(select_files)
        indb = {name: (size, mtime) for name, size, mtime in result}

        if ondisk == indb:
            return True

        if verbose:
            ondisk_names, indb_names = (d.keys() for d in (ondisk, indb))
            print(f'missing in db: {list(ondisk_names - indb_names)}')
            print(f'missing on disk: {list(indb_names - ondisk_names)}')
            common = ondisk_names & indb_names
            differing = [c for c in common if ondisk[c] != indb[c]]
            print(f'differing in size/mtime: {differing}')
        return False


@registry.mapped
class Entry:
    """Source location and old/new grouping of a .bib entry."""

    __tablename__ = 'entry'

    pk = sa.Column(sa.Integer, primary_key=True)

    file_pk = sa.Column(sa.ForeignKey('file.pk'), nullable=False)

    bibkey = sa.Column(sa.Text, sa.CheckConstraint("bibkey != ''"),
                       nullable=False)

    # old REF_ID_FIELD from bibfiles (previous hash grouping)
    refid = sa.Column(sa.Integer, sa.CheckConstraint('refid > 0'),
                      index=True)

    # current grouping: m:n with refid (splits/merges)
    hash = sa.Column(sa.Text, sa.CheckConstraint("hash != ''"),
                     index=True)

    # split-resolved refid: every srefid maps to exactly one hash
    srefid = sa.Column(sa.Integer, sa.CheckConstraint('srefid > 0'),
                       index=True)

    # new REF_ID_FIELD to ``trickle()`` into bibfiles (current hash grouping)
    id = sa.Column(sa.Integer, sa.CheckConstraint('id > 0'),
                   index=True)

    __table_args__ = (sa.UniqueConstraint(file_pk, bibkey),)

    @classmethod
    def allhash(cls, *, conn):
        select_allhash = sa.select(~sa.exists().where(cls.hash == sa.null()))
        return conn.execute(select_allhash).scalar_one()

    @classmethod
    def allid(cls, *, conn):
        select_allid = sa.select(~sa.exists().where(cls.id == sa.null()))
        return conn.execute(select_allid).scalar_one()

    @classmethod
    def onetoone(cls, *, conn):
        other = sa.orm.aliased(cls)
        diff_id = sa.and_(other.hash == cls.hash, other.id != cls.id)
        diff_hash = sa.and_(other.id == cls.hash, other.hash != cls.hash)
        select_onetoone = sa.select(~sa.exists()
                                    .select_from(cls)
                                    .where(sa.exists()
                                           .where(sa.or_(diff_id, diff_hash))))
        return conn.execute(select_onetoone).scalar_one()

    @classmethod
    def stats(cls, *, conn, out=log.info):
        out('entry stats:')
        select_n = (sa.select(File.name.label('filename'),
                              sa.func.count().label('n'))
                    .join_from(cls, File)
                    .group_by(cls.file_pk))
        result = conn.execute(select_n)
        for r in result:
            out(f'{r.filename} {r.n:d}')

        select_total = sa.select(sa.func.count()).select_from(cls)
        total = conn.execute(select_total).scalar_one()
        out(f'{total:d} entries total')

    @classmethod
    def hashstats(cls, *, conn, out=print):
        select_total = sa.select(sa.func.count(cls.hash.distinct()).label('distinct'),
                                 sa.func.count(cls.hash).label('total'))

        result = conn.execute(select_total).one()
        out(f'{result.distinct:6d}',
            f'distinct keyids (from {result.total:d} total)', sep='\t')

        sq_1 = (sa.select(File.name.label('filename'),
                          sa.func.count(cls.hash.distinct()).label('distinct'),
                          sa.func.count(cls.hash).label('total'))
                .join_from(cls, File)
                .group_by(cls.file_pk)
                .alias())

        other = sa.orm.aliased(cls)

        sq_2 = (sa.select(File.name.label('filename'),
                          sa.func.count(cls.hash.distinct()).label('unique'))
                .join_from(cls, File)
                .where(~sa.exists()
                       .where(other.hash == cls.hash)
                       .where(other.file_pk != cls.file_pk))
                .group_by(cls.file_pk)
                .alias())

        select_files = (sa.select(sa.func.coalesce(sq_2.c.unique, 0).label('unique'),
                                  sq_1.c.filename,
                                  sq_1.c.distinct,
                                  sq_1.c.total)
                        .outerjoin_from(sq_1, sq_2, sq_1.c.filename == sq_2.c.filename)
                        .order_by(sq_1.c.filename))

        result = conn.execute(select_files)
        for r in result:
            out(f'{r.unique:6d}',
                f'{r.filename} (from {r.distinct:d} distinct'
                f' of {r.total:d} total)', sep='\t')

        select_multiple = (sa.select(sa.func.count())
                           .select_from(sa.select(sa.literal(1))
                                        .select_from(cls)
                                        .group_by(cls.hash)
                                        .having(sa.func.count(cls.file_pk.distinct()) > 1)
                                        .alias()))

        multiple = conn.execute(select_multiple).scalar_one()
        out(f'{multiple:6d}', 'in multiple files', sep='\t')

    @classmethod
    def hashidstats(cls, *, conn, out=print, ref_id_field: str = REF_ID_FIELD):
        sq = (sa.select(sa.func.count(cls.refid.distinct()).label('hash_nid'))
              .where(cls.hash != sa.null())
              .group_by(cls.hash)
              .having(sa.func.count(cls.refid.distinct()) > 1).alias())

        select_nid = (sa.select(sq.c.hash_nid,
                                sa.func.count().label('n'))
                      .group_by(sq.c.hash_nid)
                      .order_by(sa.desc('n')))

        result = conn.execute(select_nid)
        for r in result:
            out(f'1 keyid {r.hash_nid:d} {ref_id_field}s: {r.n:d}')

        sq = (sa.select(sa.func.count(cls.hash.distinct()).label('id_nhash'))
              .where(cls.refid != sa.null())
              .group_by(cls.refid)
              .having(sa.func.count(cls.hash.distinct()) > 1)
              .alias())

        select_nhash = (sa.select(sq.c.id_nhash,
                                  sa.func.count().label('n'))
                        .group_by(sq.c.id_nhash)
                        .order_by(sa.desc('n')))

        result = conn.execute(select_nhash)
        for r in result:
            out(f'1 {ref_id_field} {r.id_nhash:d} keyids: {r.n:d}')

    @classmethod
    def windowed(cls, conn, *, key_column: str, size: int):
        key_column = cls.__table__.c[key_column]
        select_keys = (sa.select(key_column.distinct())
                       .order_by(key_column))

        result = conn.execute(select_keys)
        for keys in result.scalars().partitions(size):
            yield keys[0], keys[-1]


@registry.mapped
class Value:
    """Field contents (including ENTRYTYPE) of a .bib entry."""

    __tablename__ = 'value'

    entry_pk = sa.Column(sa.ForeignKey('entry.pk'), primary_key=True)

    field = sa.Column(sa.Text, sa.CheckConstraint("field != ''"),
                      primary_key=True)

    value = sa.Column(sa.Text, nullable=False)

    __table_args__ = ({'info': {'without_rowid': True}},)

    @classmethod
    def hashfields(cls, conn, *, filename, bibkey,
                   _fields=('author', 'editor', 'year', 'title')):
        # also: extra_hash, volume (if not journal, booktitle, or series)
        select_items = (sa.select(cls.field, cls.value)
                        .where(cls.field.in_(_fields))
                        .join_from(cls, Entry)
                        .filter_by(bibkey=bibkey)
                        .join(File)
                        .filter_by(name=filename))

        fields = dict(iter(conn.execute(select_items)))
        return tuple(map(fields.get, _fields))

    @classmethod
    def fieldstats(cls, *, conn, with_files: bool = False, out=print):
        tmpl = '{n:6d}\t{field}'
        select_n = (sa.select(cls.field,
                              sa.func.count().label('n'))
                    .group_by(cls.field)
                    .order_by(sa.desc('n'), 'field'))

        if with_files:
            tmpl += '\t{files}'
            select_n = select_n.join_from(Value, Entry).join(File)
            files = sa.func.replace(sa.func.group_concat(File.name.distinct()), ',', ', ')
            select_n = select_n.add_columns(files.label('files'))

        result = conn.execute(select_n)
        for r in result.mappings():
            out(tmpl.format_map(r))


def dbapi_insert(conn, model, *, column_keys: typing.List[str],
                 executemany: bool = False,
                 paramstyle: str = 'qmark'):
    """Return callable for raw dbapi insertion of ``column_keys`` into ``model``.

    Support for ``sqlite3.Cursor.executemany(<iterator>)``.
    """
    if conn.dialect.paramstyle != paramstyle:  # pragma: no cover
        raise RuntimeError('connection dialect bad paramstyle:'
                           f' {conn.dialect.paramstyle!r}'
                           f' (require: {paramstyle!r})')

    insert_model = sa.insert(model, bind=conn)
    insert_compiled = insert_model.compile(column_keys=column_keys)

    dbapi_fairy = conn.connection
    method = dbapi_fairy.executemany if executemany else dbapi_fairy.execute
    return functools.partial(method, insert_compiled.string)


def import_bibfiles(conn, bibfiles, *, ref_id_field=REF_ID_FIELD):
    """Import bibfiles with raw dbapi."""
    log.info('importing bibfiles into a new db')

    insert_file = dbapi_insert(conn, File,
                               column_keys=['name', 'size', 'mtime', 'priority'])
    insert_entry = dbapi_insert(conn, Entry,
                                column_keys=['file_pk', 'bibkey', 'refid'])
    insert_values = dbapi_insert(conn, Value,
                                 column_keys=['entry_pk', 'field', 'value'],
                                 executemany=True)

    for b in bibfiles:
        file = (b.fname.name, b.size, b.mtime, b.priority)
        file_pk = insert_file(file).lastrowid
        for e in b.iterentries():
            entry = (file_pk, e.key, e.fields.get(ref_id_field))
            entry_pk = insert_entry(entry).lastrowid

            fields = itertools.chain([(ENTRYTYPE, e.type)], e.fields.items())
            values = ((entry_pk, field, value) for field, value in fields)
            insert_values(values)


def generate_hashes(conn):
    """Assign ``Entry.hash`` to all .bib entries for grouping."""
    from .libmonster import wrds, keyid

    words = collections.Counter()
    select_titles = (sa.select(Value.value)
                     .filter_by(field='title'))
    result = conn.execute(select_titles)
    for titles in result.scalars().partitions(10_000):
        for title in titles:
            words.update(wrds(title))
    # TODO: consider dropping stop words/hapaxes from freq. distribution
    print(f'{len(words):6d}',
          f'title words (from {sum(words.values()):d} tokens)', sep='\t')

    def windowed_entries(chunksize: int = 500):
        select_files = (sa.select(File.pk)
                        .order_by(File.name))

        files = conn.execute(select_files).scalars().all()

        select_bibkeys = (sa.select(Entry.pk)
                          .filter_by(file_pk=sa.bindparam('file_pk'))
                          .order_by('pk'))

        for file_pk in files:
            result = conn.execute(select_bibkeys, {'file_pk': file_pk})
            for entry_pks in result.scalars().partitions(chunksize):
                yield entry_pks[0], entry_pks[-1]

    select_bfv = (sa.select(Entry.pk,
                            Value.field,
                            Value.value)
                  .join_from(Value, Entry)
                  .where(Entry.pk.between(sa.bindparam('first'), sa.bindparam('last')))
                  .where(Value.field != ENTRYTYPE)
                  .order_by('pk'))

    assert conn.dialect.paramstyle == 'qmark'
    update_entry = (sa.update(Entry, bind=conn)
                    .values(hash=sa.bindparam('hash'))
                    .where(Entry.pk == sa.bindparam('entry_pk'))
                    .compile().string)
    update_entry = functools.partial(conn.connection.executemany, update_entry)

    groupby_entry_pk = functools.partial(itertools.groupby,
                                         key=operator.attrgetter('pk'))

    for first, last in windowed_entries():
        result = conn.execute(select_bfv, {'first': first, 'last': last})
        update_entry(((keyid({r.field: r.value for r in grp}, words), entry_pk)
                      for entry_pk, grp in groupby_entry_pk(result)))


def assign_ids(conn, *, verbose: bool = False):
    """Assign ``Entry.id`` to all .bib entries to establish new grouping."""
    assert Entry.allhash(conn=conn)

    reset = reset_entries(conn)
    print(f'{reset:d} entries')

    n_split = resolve_splits(conn, verbose=verbose)
    print(f'{n_split:d} splitted')

    other = sa.orm.aliased(Entry)

    no_splits = sa.select(~sa.exists()
                          .select_from(Entry)
                          .where(sa.exists()
                                 .where(other.srefid == Entry.srefid)
                                 .where(other.hash != Entry.hash)))

    assert conn.execute(no_splits).scalar_one()

    n_merged = resolve_merges(conn, verbose=verbose)
    print(f'{n_merged:d} merged')

    n_unchanged = assign_unchanged(conn)
    print(f'{n_unchanged:d} unchanged')

    no_merges = sa.select(~sa.exists()
                          .select_from(Entry)
                          .where(sa.exists()
                                 .where(other.hash == Entry.hash)
                                 .where(other.id != Entry.id)))

    assert conn.execute(no_merges).scalar_one()

    n_identified = update_identified(conn)
    print(f'{n_identified:d} identified (new/separated)')

    n_new = assign_new_and_separated(conn)
    print(f'{n_new:d} new ids (new/separated)')

    assert Entry.allid(conn=conn)
    assert Entry.onetoone(conn=conn)

    count_superseded = (sa.select(sa.func.count())
                        .where(Entry.id != Entry.srefid))

    n_superseded = conn.execute(count_superseded).scalar_one()
    print(f'{n_superseded:d} supersede pairs')


def reset_entries(conn):
    """Set srefid = refid and id = NULL on all entries."""
    update_entries = (sa.update(Entry)
                      .values(id=sa.null(),
                              srefid=Entry.refid))

    return conn.execute(update_entries).rowcount


def resolve_splits(conn, *, verbose: bool = False):
    """Keep srefid = refid only for entries from the most similar hash group."""
    other = sa.orm.aliased(Entry)

    select_split = (sa.select(Entry.refid,
                              Entry.hash,
                              File.name.label('filename'),
                              Entry.bibkey)
                    .join_from(Entry, File)
                    .where(sa.exists()
                           .where(other.refid == Entry.refid)
                           .where(other.hash != Entry.hash))
                    .order_by('refid', 'hash', 'filename', 'bibkey'))

    update_split = (sa.update(Entry)
                    .where(Entry.refid == sa.bindparam('eq_refid'))
                    .where(Entry.hash != sa.bindparam('ne_hash'))
                    .values(srefid=sa.null()))

    n_split = 0

    for refid, group in groupby_first(conn.execute(select_split)):
        n_split += len(group)

        _, _, new = split_old_cand_new(conn, group, refid=refid)

        params = {'eq_refid': refid, 'ne_hash': new}
        separated = conn.execute(update_split, params).rowcount

        if verbose:
            for row in group:
                print(row)
            for row in group:
                hashfields = Value.hashfields(conn,
                                              filename=row.filename,
                                              bibkey=row.bibkey)
                print('\t%r, %r, %r, %r' % hashfields)
            print(f'-> {new}')
            print(f'{refid:d}: {separated:d} separated from {new}\n')

    return n_split


def split_old_cand_new(conn, group, *, refid: int,
                       _get_merged_entry=Database._get_merged_entry):
    old = _get_merged_entry(conn, key=refid)

    cand = [(hash_, _get_merged_entry(conn, key=hash_))
            for hash_ in unique(r.hash for r in group)]

    new = min(cand, key=lambda p: distance(old, p[1]))[0]

    return old, cand, new


def resolve_merges(conn, *, verbose: bool = False):
    """Set id = srefid of the most similar srefid group."""
    other = sa.orm.aliased(Entry)

    select_merge = (sa.select(Entry.hash,
                              Entry.srefid,
                              File.name.label('filename'),
                              Entry.bibkey)
                    .join_from(Entry, File)
                    .where(sa.exists()
                           .where(other.hash == Entry.hash)
                           .where(other.srefid != Entry.srefid))
                    .order_by('hash',
                              Entry.srefid.desc(),
                              'filename', 'bibkey'))

    merge = functools.partial(merge_new_cand_old, conn,
                              keyfunc=operator.attrgetter('srefid'))

    update_merge = (sa.update(Entry, bind=conn)
                    .where(Entry.hash == sa.bindparam('eq_hash'))
                    .where(Entry.srefid != sa.bindparam('ne_srefid'))
                    .values(id=sa.bindparam('new_id')))

    n_merged = 0

    for hash_, group in groupby_first(conn.execute(select_merge)):
        n_merged += len(group)

        _, _, old = merge(group, hash_=hash_)

        params = {'eq_hash': hash_, 'ne_srefid': old, 'new_id': old}
        merged = conn.execute(update_merge, params).rowcount

        if verbose:
            for row in group:
                print(row)
            for row in group:
                hashfields = Value.hashfields(conn,
                                              filename=row.filename,
                                              bibkey=row.bibkey)
                print('\t%r, %r, %r, %r' % hashfields)
            print(f'-> {old}')
            print(f'{hash_}: {merged:d} merged into {old:d}\n')

    return n_merged


def merge_new_cand_old(conn, group, *, hash_: str, keyfunc,
                       _get_merged_entry=Database._get_merged_entry):
    new = _get_merged_entry(conn, key=hash_)

    cand = [(key, _get_merged_entry(conn, key=key))
            for key in unique(keyfunc(r) for r in group)]

    old = min(cand, key=lambda p: distance(new, p[1]))[0]

    return new, cand, old


def assign_unchanged(conn):
    """Set id = srefid on unchanged entries."""
    update_unchanged = (sa.update(Entry)
                        .where(Entry.id == sa.null())
                        .where(Entry.srefid != sa.null())
                        .values(id=Entry.srefid))

    return conn.execute(update_unchanged).rowcount


def update_identified(conn):
    """Set id on identified entries."""
    other = sa.orm.aliased(Entry)

    update_identified = (sa.update(Entry)
                         .where(Entry.refid == sa.null())
                         .where(sa.exists()
                                .where(other.hash == Entry.hash)
                                .where(other.id != sa.null()))
                         .values(id=(sa.select(other.id)
                                     .where(other.hash == Entry.hash)
                                     .where(other.id != sa.null())
                                     .scalar_subquery())))

    return conn.execute(update_identified).rowcount


def assign_new_and_separated(conn):
    """Assign new ids to hash groups of new/separated entries."""
    select_nextid = sa.select(sa.func.coalesce(sa.func.max(Entry.refid), 0) + 1)

    select_new = (sa.select(Entry.hash)
                  .where(Entry.id == sa.null())
                  .group_by(Entry.hash)
                  .order_by('hash'))

    assert conn.dialect.paramstyle == 'qmark'
    update_new = (sa.update(Entry, bind=conn)
                  .values(id=sa.bindparam('new_id'))
                  .where(Entry.hash == sa.bindparam('eq_hash'))
                  .compile().string)

    nextid = conn.execute(select_nextid).scalar_one()

    new_hashes = conn.execute(select_new)

    params = ((id_, hash_) for id_, (hash_,) in enumerate(new_hashes, nextid))

    dbapi_cursor = conn.connection.executemany(update_new, params)
    # https://docs.python.org/3/library/sqlite3.html#sqlite3.Cursor.rowcount
    return 0 if dbapi_cursor.rowcount == -1 else dbapi_cursor.rowcount
