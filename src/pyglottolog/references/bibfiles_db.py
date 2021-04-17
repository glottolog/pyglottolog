"""Load bibfiles into sqlite3, hash, assign ids (split/merge)."""

import typing
import logging
import difflib
import pathlib
import operator
import functools
import itertools
import contextlib
import collections

import sqlalchemy as sa
import sqlalchemy.orm
from clldutils import jsonlib
from csvw import dsv

from .. import _compat
from . import bibtex
from ..util import unique, group_first

__all__ = ['Database']

UNION_FIELDS = {'fn', 'asjp_name', 'isbn'}

IGNORE_FIELDS = {'crossref', 'numnote', 'glotto_id'}

ENCODING = 'utf-8'

SQLALCHEMY_FUTURE = True

ENTRYTYPE = 'ENTRYTYPE'


log = logging.getLogger('pyglottolog')


registry = sa.orm.registry()


class Database(object):
    """Collection of parsed .bib files loaded into a SQLite database."""

    @classmethod
    def from_bibfiles(cls, bibfiles, filepath, *, rebuild: bool = False,
                      page_size: typing.Optional[int] = 32_768,
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

    def __init__(self, filepath):
        self.filepath = pathlib.Path(filepath)
        self._engine = sa.create_engine(f'sqlite:///{self.filepath}',
                                        future=SQLALCHEMY_FUTURE,
                                        paramstyle='qmark')

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
            manager = contextlib.closing if closing else _compat.nullcontext
            with manager(result) as result:
                yield result

    def is_uptodate(self, bibfiles, *, verbose: bool = False):
        """Does the db have the same filenames, sizes, and mtimes as ``bibfiles``?"""
        with self.connect() as conn:
            return File.same_as(conn, bibfiles, verbose=verbose)

    def stats(self, *, field_files: bool = False):
        with self.connect() as conn:
            Entry.stats(conn=conn)
            Value.fieldstats(conn=conn, with_files=field_files)
            Entry.hashstats(conn=conn)
            Entry.hashidstats(conn=conn)

    def to_bibfile(self, filepath, *, encoding: str = ENCODING):
        bibtex.save(self.merged(), str(filepath), sortkey=None, encoding=encoding)

    def to_csvfile(self, filename, *, dialect='excel', encoding: str = ENCODING):
        """Write a CSV file with one row for each entry in each bibfile."""
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

    def to_replacements(self, filename):
        """Write a JSON file with 301s from merged glottolog_ref_ids."""
        select_pairs = (sa.select(Entry.refid.label('id'),
                                  Entry.id.label('replacement'))
                        .where(Entry.id != Entry.refid)
                        .order_by('replacement'))

        with self.execute(select_pairs) as result:
            pairs = result.mappings().all()

        with jsonlib.update(filename, default=[], indent=4) as repls:
            # RowMapping is not JSON serializable
            repls.extend(map(dict, pairs))

    def trickle(self, bibfiles):
        """Write new/changed glottolog_ref_ids back into ``bibfiles``."""
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
                    old = fields.pop('glottolog_ref_id', None)
                    assert old == refid
                    if old is None:
                        added += 1
                    else:
                        changed += 1
                    fields['glottolog_ref_id'] = new

                print(f'{changed:d} changed {added:d} added in {bf.id}')
                bf.save(entries)

    def merged(self):
        """Yield merged ``(bibkey, (entrytype, fields))`` entries."""
        for (id, hash), grp in self:
            entrytype, fields = self._merged_entry(grp)
            fields['glottolog_ref_id'] = f'{id:d}'
            yield hash, (entrytype, fields)

    def __iter__(self, *, chunksize: int = 100):
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

        get_id_hash = operator.itemgetter(0, 1)

        get_field = operator.itemgetter(2)

        with self.connect() as conn:
            for first, last in Entry.windowed(conn, key_column='id', size=chunksize):
                result = conn.execute(select_values, {'first': first, 'last': last})
                for id_hash, grp in itertools.groupby(result, key=get_id_hash):
                    fields = [(field,
                               [(vl, fn, bk) for _, _, _, vl, fn, bk in g])
                              for field, g in itertools.groupby(grp, key=get_field)]
                    yield id_hash, fields

    def __getitem__(self, key: typing.Union[typing.Tuple[str, str], int, str]):
        """Entry by (fn, bk) or merged entry by refid (old grouping) or hash (current grouping)."""
        if not isinstance(key, (tuple, int, str)):
            raise TypeError(f'key must be tuple, int, or str: {key!r}')  # pragma: no cover

        with self.connect() as conn:
            if isinstance(key, tuple):
                filename, bibkey = key
                entrytype, fields = self._entry(conn, filename, bibkey)
            else:
                grp = self._entrygrp(conn, key)
                entrytype, fields = self._merged_entry(grp)

        return key, (entrytype, fields)

    @staticmethod
    def _entry(conn, filename: str, bibkey: str):
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

    @staticmethod
    def _merged_entry(grp,
                      *, union=UNION_FIELDS, ignore=IGNORE_FIELDS,
                      raw: bool = False):
        # TODO: consider implementing (a subset of?) onlyifnot logic:
        # {'address': 'publisher', 'lgfamily': 'lgcode', 'publisher': 'school',
        # 'journal': 'booktitle'}
        fields = {field: values[0][0] if field not in union
                  else ', '.join(unique(vl for vl, _, _ in values))
                  for field, values in grp if field not in ignore}

        src = {fn.rpartition('.bib')[0] or fn
               for _, values in grp
               for _, fn, _ in values}
        fields['src'] = ', '.join(sorted(src))

        srctrickle = {'%s#%s' % (fn.rpartition('.bib')[0] or fn, bk)
                      for _, values in grp
                      for _, fn, bk in values}
        fields['srctrickle'] = ', '.join(sorted(srctrickle))

        if raw:
            return fields
        entrytype = fields.pop(ENTRYTYPE)
        return entrytype, fields

    @staticmethod
    def _entrygrp(conn, key,
                  *, get_field=operator.itemgetter(0)):
        select_values = (sa.select(Value.field,
                                   Value.value,
                                   File.name.label('filename'),
                                   Entry.bibkey)
                         .join_from(Entry, File).join(Value)
                         .where((Entry.refid if isinstance(key, int) else Entry.hash) == key)
                         .order_by('field',
                                   File.priority.desc(),
                                   'filename', 'bibkey'))

        result = conn.execute(select_values)
        grouped = itertools.groupby(result, key=get_field)
        grp = [(field,
                [(vl, fn, bk) for _, vl, fn, bk in g])
               for field, g in grouped]

        if not grp:
            raise KeyError(key)
        return grp

    def show_splits(self):
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
            for refid, group in group_first(result):
                self._print_group(conn, group)
                old = self._merged_entry(self._entrygrp(conn, refid), raw=True)
                cand = [(hs, self._merged_entry(self._entrygrp(conn, hs), raw=True))
                        for hs in unique(hs for _, hs, _, _ in group)]
                new = min(cand, key=lambda p: distance(old, p[1]))[0]
                print(f'-> {new}\n')

    def show_merges(self):
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
            result = conn.execute(select_entries)
            for hash_, group in group_first(result):
                self._print_group(conn, group)
                new = self._merged_entry(self._entrygrp(conn, hash_), raw=True)
                cand = [(ri, self._merged_entry(self._entrygrp(conn, ri), raw=True))
                        for ri in unique(ri for _, ri, _, _ in group)]
                old = min(cand, key=lambda p: distance(new, p[1]))[0]
                print(f'-> {old}\n')

    @staticmethod
    def _print_group(conn, group, *, out=print):
        for row in group:
            out(row)
        for row in group:
            hashfields = Value.hashfields(conn,
                                          filename=row['filename'],
                                          bibkey=row['bibkey'])
            out('\t%r, %r, %r, %r' % hashfields)

    def _show(self, sql):
        with self.connect() as conn:
            result = conn.execute(sql)
            for hash, group in group_first(result):
                self._print_group(conn, group)
                print()

    def show_identified(self):
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
        other = sa.orm.aliased(Entry)

        select_entries = (sa.select(Entry.hash,
                                    File.name.label('filename'),
                                    Entry.bibkey)
                          .join_from(Entry, File)
                          .where(Entry.refid == sa.null())
                          .where(sa.exists()
                                 .where(other.refid == sa.null())
                                 .where(other.hash == Entry.hash))
                          .order_by('hash', 'filename', 'bibkey'))

        self._show(select_entries)


@registry.mapped
class File:

    __tablename__ = 'file'

    pk = sa.Column(sa.Integer, primary_key=True)

    name = sa.Column(sa.Text, nullable=False, unique=True)

    size = sa.Column(sa.Integer, nullable=False)
    mtime = sa.Column(sa.DateTime, nullable=False)

    priority = sa.Column(sa.Integer, nullable=False)

    @classmethod
    def same_as(cls, conn, bibfiles, *, verbose: bool = False):
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

    __tablename__ = 'entry'

    pk = sa.Column(sa.Integer, primary_key=True)

    file_pk = sa.Column(sa.ForeignKey('file.pk'), nullable=False)

    bibkey = sa.Column(sa.Text, nullable=False)

    # old glottolog_ref_id from bibfiles (previous hash groupings)
    refid = sa.Column(sa.Integer, index=True)

    # current groupings, m:n with refid (splits/merges):
    hash = sa.Column(sa.Text, index=True)

    # split-resolved refid (every srefid maps to exactly one hash):
    srefid = sa.Column(sa.Integer, index=True)

    # new glottolog_ref_id save to bibfiles (current hash groupings):
    id = sa.Column(sa.Integer, index=True)

    __table_args__ = (sa.UniqueConstraint(file_pk, bibkey),)

    @classmethod
    def allhash(cls, *, conn):
        select_allhash = sa.select(~sa.exists().where(cls.hash == sa.null()))
        return conn.scalar(select_allhash)

    @classmethod
    def allid(cls, *, conn):
        select_allid = sa.select(~sa.exists().where(cls.id == sa.null()))
        return conn.scalar(select_allid)

    @classmethod
    def onetoone(cls, *, conn):
        other = sa.orm.aliased(cls)
        diff_id = sa.and_(other.hash == cls.hash, other.id != cls.id)
        diff_hash = sa.and_(other.id == cls.hash, other.hash != cls.hash)
        select_onetoone = sa.select(~sa.exists()
                                    .select_from(cls)
                                    .where(sa.exists()
                                           .where(sa.or_(diff_id, diff_hash))))
        return conn.scalar(select_onetoone)

    @classmethod
    def stats(cls, *, conn, out=log.info):
        out('entry stats:')
        select_n = (sa.select(File.name.label('filename'),
                              sa.func.count().label('n'))
                    .join_from(cls, File)
                    .group_by(cls.file_pk))
        result = conn.execute(select_n)
        out('\n'.join(f'{r.filename} {r.n:d}' for r in result))

        select_total = sa.select(sa.func.count()).select_from(cls)
        total = conn.scalar(select_total)
        out(f'{total:d} entries total')

    @classmethod
    def hashstats(cls, *, conn, out=print):
        select_total = sa.select(sa.func.count(cls.hash.distinct()).label('distinct'),
                                 sa.func.count(cls.hash).label('total'))

        result = conn.execute(select_total).one()
        out(f'{result.distinct:d}\tdistinct keyids'
            f' (from {result.total:d} total)')

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
            out(f'{r.unique:d}\t{r.filename}'
                f' (from {r.distinct:d} distinct of {r.total:d} total)')

        select_multiple = (sa.select(sa.func.count())
                           .select_from(sa.select(sa.literal(1))
                                        .select_from(cls)
                                        .group_by(cls.hash)
                                        .having(sa.func.count(cls.file_pk.distinct()) > 1)
                                        .alias()))

        multiple = conn.scalar(select_multiple)
        out(f'{multiple:d}\tin multiple files')

    @classmethod
    def hashidstats(cls, *, conn, out=print):
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
            out(f'1 keyid {r.hash_nid:d} glottolog_ref_ids: {r.n:d}')

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
            out(f'1 glottolog_ref_id {r.id_nhash:d} keyids: {r.n:d}')

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

    __tablename__ = 'value'

    entry_pk = sa.Column(sa.ForeignKey('entry.pk'), primary_key=True)

    field = sa.Column(sa.Text, primary_key=True)

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
        tmpl = '{n:d}\t{field}'
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
                 executemany: bool = False):
    assert conn.dialect.paramstyle == 'qmark'

    insert_model = sa.insert(model, bind=conn)
    insert_compiled = insert_model.compile(column_keys=column_keys)

    dbapi_fairy = conn.connection
    method = dbapi_fairy.executemany if executemany else dbapi_fairy.execute
    return functools.partial(method, insert_compiled.string)


def import_bibfiles(conn, bibfiles):
    """Import bibfiles with raw dbapi using ``.executemany(<iterable>)``."""
    log.info('importing bibfiles into a new db')

    insert_file =  dbapi_insert(conn, File,
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
            entry = (file_pk, e.key, e.fields.get('glottolog_ref_id'))
            entry_pk = insert_entry(entry).lastrowid

            fields = itertools.chain([(ENTRYTYPE, e.type)], e.fields.items())
            values = ((entry_pk, field, value) for field, value in fields)
            insert_values(values)


def generate_hashes(conn):
    from .libmonster import wrds, keyid

    words = collections.Counter()
    select_titles = (sa.select(Value.value)
                     .filter_by(field='title'))
    result = conn.execute(select_titles)
    for titles in result.scalars().partitions(10_000):
        for title in titles:
            words.update(wrds(title))
    # TODO: consider dropping stop words/hapaxes from freq. distribution
    print(f'{len(words):d} title words (from {sum(words.values()):d} tokens)')

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

    get_entry_pk = operator.itemgetter(0)

    for first, last in windowed_entries():
        result = conn.execute(select_bfv, {'first': first, 'last': last})
        grouped = itertools.groupby(result, key=get_entry_pk)
        update_entry(((keyid({k: v for _, k, v in grp}, words), entry_pk)
                      for entry_pk, grp in grouped))


def assign_ids(conn, *, verbose: bool = False):
    assert Entry.allhash(conn=conn)

    merged_entry = Database._merged_entry
    entrygrp = Database._entrygrp
    other = sa.orm.aliased(Entry)

    reset_entries = sa.update(Entry).values(id=sa.null(), srefid=Entry.refid)
    reset = conn.execute(reset_entries).rowcount
    print(f'{reset:d} entries')

    # resolve splits: srefid = refid only for entries from the most similar hash group
    nsplit = 0

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

    for refid, group in group_first(conn.execute(select_split)):
        old = merged_entry(entrygrp(conn, refid), raw=True)
        nsplit += len(group)
        cand = [(hs, merged_entry(entrygrp(conn, hs), raw=True))
                for hs in unique(hs for _, hs, _, _ in group)]
        new = min(cand, key=lambda p: distance(old, p[1]))[0]
        params = {'eq_refid': refid, 'ne_hash': new}
        separated = conn.execute(update_split, params).rowcount
        if verbose:
            for row in group:
                print(row)
            for _, _, fn, bk in group:
                hashfields = Value.hashfields(conn, filename=fn, bibkey=bk)
                print('\t%r, %r, %r, %r' % hashfields)
            print(f'-> {new}')
            print(f'{refid:d}: {separated:d} separated from {new}\n')
    print(f'{nsplit:d} splitted')

    nosplits = sa.select(~sa.exists()
                         .select_from(Entry)
                         .where(sa.exists()
                                .where(other.srefid == Entry.srefid)
                                .where(other.hash != Entry.hash)))
    assert conn.scalar(nosplits)

    # resolve merges: id = srefid of the most similar srefid group
    nmerge = 0

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

    update_merge = (sa.update(Entry, bind=conn)
                    .where(Entry.hash == sa.bindparam('eq_hash'))
                    .where(Entry.srefid != sa.bindparam('ne_srefid'))
                    .values(id=sa.bindparam('new_id')))

    for hash, group in group_first(conn.execute(select_merge)):
        new = merged_entry(entrygrp(conn, hash), raw=True)
        nmerge += len(group)
        cand = [(ri, merged_entry(entrygrp(conn, ri), raw=True))
                for ri in unique(ri for _, ri, _, _ in group)]
        old = min(cand, key=lambda p: distance(new, p[1]))[0]
        params = {'eq_hash': hash, 'ne_srefid': old, 'new_id': old}
        merged = conn.execute(update_merge, params).rowcount
        if verbose:
            for row in group:
                print(row)
            for _, _, fn, bk in group:
                print('\t%r, %r, %r, %r' % Value.hashfields(conn,
                                                            filename=fn,
                                                            bibkey=bk))
            print(f'-> {old}')
            print(f'{hash}: {merged:d} merged into {old:d}\n')
    print(f'{nmerge:d} merged')

    # unchanged entries
    update_unchanged = (sa.update(Entry)
                        .where(Entry.id == sa.null())
                        .where(Entry.srefid != sa.null())
                        .values(id=Entry.srefid))
    unchanged = conn.execute(update_unchanged).rowcount
    print(f'{unchanged:d} unchanged')

    nomerges = sa.select(~sa.exists().select_from(Entry)
                         .where(sa.exists()
                                .where(other.hash == Entry.hash)
                                .where(other.id != Entry.id)))
    assert conn.scalar(nomerges)

    # identified
    update_identified = (sa.update(Entry)
                         .where(Entry.refid == sa.null())
                         .where(sa.exists()
                                .where(other.hash == Entry.hash)
                                .where(other.id != sa.null()))
                         .values(id=(sa.select(other.id)
                                     .where(other.hash == Entry.hash)
                                     .where(other.id != sa.null())
                                     .scalar_subquery())))
    identified = conn.execute(update_identified).rowcount
    print(f'{identified:d} identified (new/separated)')

    # assign new ids to hash groups of separated/new entries
    select_nextid = sa.select(sa.func.coalesce(sa.func.max(Entry.refid), 0) + 1)
    nextid = conn.scalar(select_nextid)

    select_new = (sa.select(Entry.hash)
                  .where(Entry.id == sa.null())
                  .group_by(Entry.hash)
                  .order_by('hash'))

    assert conn.dialect.paramstyle == 'qmark'
    update_new = (sa.update(Entry, bind=conn)
                  .values(id=sa.bindparam('new_id'))
                  .where(Entry.hash == sa.bindparam('eq_hash'))
                  .compile().string)

    params = ((id, hash) for id, (hash,) in enumerate(conn.execute(select_new), nextid))
    dbapi_rowcount = conn.connection.executemany(update_new, params).rowcount
    # https://docs.python.org/2/library/sqlite3.html#sqlite3.Cursor.rowcount
    new = 0 if dbapi_rowcount == -1 else dbapi_rowcount
    print(f'{new:d} new ids (new/separated)')

    assert Entry.allid(conn=conn)
    assert Entry.onetoone(conn=conn)

    # supersede relation
    select_superseded = (sa.select(sa.func.count())
                         .where(Entry.id != Entry.srefid))
    superseded = conn.scalar(select_superseded)
    print(f'{superseded:d} supersede pairs')


def distance(left, right,
             *, weight={'author': 3, 'year': 3, 'title': 3, ENTRYTYPE: 2}):
    """Simple measure of the difference between two bibtex-field dicts."""
    if not (left or right):
        return 0.0

    keys = left.keys() & right.keys()
    if not keys:
        return 1.0

    weights = {k: weight.get(k, 1) for k in keys}
    ratios = (w * difflib.SequenceMatcher(None, left[k], right[k]).ratio()
              for k, w in weights.items())
    return 1 - (sum(ratios) / sum(weights.values()))
