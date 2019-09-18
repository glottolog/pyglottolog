# coding: utf8
from __future__ import unicode_literals, print_function, division
from collections import defaultdict, Counter
import os
import sys
import re
import argparse
import subprocess
from json import dumps
from string import Template
import functools

from termcolor import colored
from clldutils.clilib import command, ParserError
from clldutils.misc import slug
from clldutils.color import qualitative_colors
from clldutils.markup import Table
from clldutils.path import Path, write_text, read_text, git_describe
from csvw.dsv import UnicodeWriter

import pyglottolog
import pyglottolog.iso
from .languoids import Languoid, Reference
from . import fts
from . import lff
from . import cldf
from .monster import compile
from .references import evobib
from .references import ldh
from .util import message, sprint
from .metadata import prepare_release
# Make sure we import all link providers:
from .links import *  # noqa: F401, F403
from .links.util import LinkProvider


def assert_repos(func):
    @functools.wraps(func)
    def wrapper(args, **kw):
        if args.repos is None:
            raise ParserError('Invalid Glottolog data directory specified as --repos')
        return func(args, **kw)
    return wrapper


@command()
@assert_repos
def release(args):
    """
    Write release info to .zenodo.json, CITATION.md and CONTRIBUTORS.md
    """
    prepare_release(args.repos, input('version: '))


@command()
@assert_repos
def languoids(args):
    """
    glottolog --repos=. languoids [--output=OUTDIR] [--version=VERSION]
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--output', help='An existing directory for the output', default='.', type=Path)
    parser.add_argument(
        '--version', help='Version string if it cannot be inferred', default=args.repos.describe())
    xargs = parser.parse_args(args.args)
    res = args.repos.write_languoids_table(xargs.output, xargs.version)
    print('Lagnuoids table written to')
    for p in res:
        print('{0}'.format(p))


@command()
@assert_repos
def htmlmap(args, min_langs_for_legend_item=10):
    """
    glottolog --repos=. htmlmap [OUTDIR] [GLOTTOCODES]
    """
    nodes = {n.id: n for n in args.repos.languoids()}
    legend = Counter()

    glottocodes = None
    if len(args.args) > 1:
        glottocodes = read_text(args.args[1]).split()

    langs = []
    for n in nodes.values():
        if ((glottocodes is None and n.level == args.repos.languoid_levels.language) or (glottocodes and n.id in glottocodes)) and n.latitude != None:
            fid = n.lineage[0][1] if n.lineage else n.id
            if (not nodes[fid].category.startswith('Pseudo')) or fid == n.id:
                langs.append((n, fid))
                legend.update([fid])

    color_map = [fid for fid, _ in legend.most_common()]
    color_map = dict(zip(color_map, qualitative_colors(len(color_map))))
    print(color_map)

    def l2f(t):
        n, fid = t
        lon, lat = n.longitude, n.latitude
        if lon <= -26:
            lon += 360  # make the map pacific-centered.

        return {
            "geometry": {"coordinates": [lon, lat], "type": "Point"},
            "id": n.id,
            "properties": {
                "name": n.name,
                "color": color_map[fid],
                "family": nodes[fid].name,
                "family_id": fid,
            },
            "type": "Feature"
        }

    def legend_item(fid, c):
        return \
            '<span style="background-color: {0}; border: 1px solid black;">'\
            '&nbsp;&nbsp;&nbsp;</span> '\
            '<a href="https://glottolog.org/resource/languoid/id/{1}">{2}</a> ({3})'.format(
                color_map[fid], fid, nodes[fid].name, c)

    geojson = {
        "features": list(map(l2f, langs)),
        "properties": {
            "legend": {
                fid: legend_item(fid, c) for fid, c in legend.most_common() if
                c >= min_langs_for_legend_item},
        },
        "type": "FeatureCollection"
    }

    def rendered_template(name, **kw):
        return Template(read_text(
            Path(pyglottolog.__file__).parent.joinpath('templates', 'htmlmap', name))
        ).substitute(**kw)

    jsname = 'glottolog_map.json'
    outdir = Path('.') if not args.args else Path(args.args[0])
    write_text(
        outdir.joinpath(jsname),
        rendered_template('htmlmap.js', geojson=dumps(geojson, indent=4)))
    html = outdir.joinpath('glottolog_map.html')
    write_text(
        html,
        rendered_template(
            'htmlmap.html',
            version=git_describe(args.repos.repos),
            jsname=jsname,
            nlangs=len(langs)))
    print(html.resolve().as_uri())


@command()
@assert_repos
def iso2codes(args):
    """
    Map ISO codes to the list of all Glottolog languages and dialects subsumed "under" it.
    """
    nodes = list(args.repos.languoids())

    res = {}
    for node in nodes:
        if node.iso:
            res[node.id] = (node.iso, set())

    for node in nodes:
        if node.level == args.repos.languoid_levels.family or node.id in res:
            continue
        for nid in res:
            matched = False
            for l in node.lineage:
                if l[1] == nid:
                    res[nid][1].add(node.id)
                    matched = True
                    break
            if matched:
                break

    outdir = Path('.') if not args.args else Path(args.args[0])
    with UnicodeWriter(outdir / 'iso2glottocodes.csv') as writer:
        writer.writerow(['iso', 'glottocodes'])
        for gc, (iso, gcs) in res.items():
            writer.writerow([iso, ';'.join([gc] + list(gcs))])


@command('cldf')
@assert_repos
def _cldf(args):
    """glottolog cldf PATH/TO/glottolog-cldf
    """
    cldf.cldf(args.repos, Path(args.args[0]), args.log)


@command('evobib')
@assert_repos
def _evobib(args):  # pragma: no cover
    evobib.download(args.repos.bibfiles['evobib.bib'], args.log)


@command('ldh')
@assert_repos
def _ldh(args):  # pragma: no cover
    ldh.download(args.repos.bibfiles['ldh.bib'], args.log)


@command()
@assert_repos
def roundtrip(args):
    """Load/save the bibfile with the given name."""
    args.repos.bibfiles[args.args[0]].roundtrip()


@command()
@assert_repos
def bibfiles_db(args):
    """(Re-)create bibfiles sqlite3 database in the current directory."""
    args.repos.bibfiles.to_sqlite(rebuild=True)


@command()
@assert_repos
def copy_benjamins(args, name='benjamins.bib'):  # pragma: no cover
    """
    glottolog copy_benjamins /path/to/benjamins/benjamins.bib
    """
    args.repos.bibfiles[name].update(args.args[0], log=args.log)


@command()
@assert_repos
def elcat_diff(args):  # pragma: no cover
    from pyglottolog.links.endangeredlanguages import read

    langs = list(args.repos.languoids())
    gl_isos = {l.iso for l in langs if l.iso}
    gl_names = {l.name for l in langs}
    aes = {}
    for l in langs:
        if l.endangerment and l.endangerment.source.id == 'ElCat':
            m = re.search('\((?P<id>[0-9]+)\-', l.endangerment.comment or '')
            if m:
                aes[int(m.group('id'))] = l

    in_gl = {}
    for l in langs:
        if l.identifier.get('multitree'):
            in_gl[l.identifier['multitree']] = l

    c = Counter()
    for i, l in enumerate(read()):
        if len(l.isos) > 1:
            print('+++ multiple codes: {0.name} [{0.id}][{0.isos}]'.format(l))
            c.update(['multiple'])
            continue
        if not l.isos:
            print('--- no codes: {0.name} [{0.id}]'.format(l))
            c.update(['none'])
            continue

        iso = l.isos[0]
        if iso in gl_isos:
            c.update(['iso match'])
            continue

        if iso in in_gl:
            c.update(['LL match'])
            continue

        if l.id in aes:
            c.update(['AES match'])
            continue

        if len(l.name) > 5 and l.name in gl_names:
            c.update(['name match'])
            continue

        print('~~~ no match: {0.name} [{0.id}][{0.isos}]'.format(l))
        c.update(['no match'])

    for k, v in c.most_common():
        print(k, v)
    print(sum(c.values()))


@command()
@assert_repos
def update_links(args):
    langs = list(args.repos.languoids())
    updated = set()
    for cls in LinkProvider.__subclasses__():
        name = cls.__name__.lower()
        if (not args.args) or (name in args.args):
            args.log.info('updating {0} links ...'.format(name))
            i = 0
            for i, l in enumerate(cls().iterupdated(langs), start=1):
                l.write_info()
                updated.add(l.id)
            args.log.info('... {0} done'.format(i))
    print('{0} languoids updated'.format(len(updated)))


@command()
@assert_repos
def isobib(args):  # pragma: no cover
    """Update iso6393.bib - the file of references for ISO 639-3 change requests."""
    pyglottolog.iso.bibtex(args.repos, args.log)


@command()
@assert_repos
def isoretirements(args):  # pragma: no cover
    """Update retirement info in language info files."""
    pyglottolog.iso.retirements(args.repos, args.log)


def existing_lang(args):
    if not args.args:
        raise ParserError('No languoid specified')
    lang = args.repos.languoid(args.args[0])
    if not lang:
        raise ParserError('Invalid languoid spec')
    return lang


@command()
@assert_repos
def show(args):
    """Display details of a Glottolog object.

    glottolog --repos=. show <GLOTTOCODE>|<ISO-CODE>|<BIBTEXKEY>
    """
    if args.args and ':' in args.args[0]:
        if args.args[0].startswith('**'):
            ref = Reference.from_string(args.args[0])
        else:
            ref = Reference(key=args.args[0])
        sprint('Glottolog reference {0}'.format(ref), attrs=['bold', 'underline'])
        print()
        src = ref.get_source(args.repos)
        sprint(src.text())
        print()
        sprint(src)
        return
    lang = existing_lang(args)
    print()
    sprint('Glottolog languoid {0}'.format(lang.id), attrs=['bold', 'underline'])
    print()
    sprint('Classification:', attrs=['bold', 'underline'])
    args.repos.ascii_tree(lang, maxlevel=1)
    print()
    sprint('Info:', attrs=['bold', 'underline'])
    sprint('Path: {0}'.format(lang.fname), 'green', attrs=['bold'])
    sources = lang.sources
    if sources:
        del lang.cfg['sources']['glottolog']
        del lang.cfg['sources']
    for line in lang.cfg.write_string().split('\n'):
        if not line.startswith('#'):
            sprint(line, None, attrs=['bold'] if line.startswith('[') else [])
    sprint('Sources:', attrs=['bold', 'underline'])
    for src in sources:
        src = src.get_source(args.repos)
        sprint(src.id, color='green')
        sprint(src.text())
        print()


@command()
@assert_repos
def edit(args):
    """Open a languoid's INI file in a text editor.

    glottolog --repos=. edit <GLOTTOCODE>|<ISO-CODE>
    """
    lang = existing_lang(args)
    if sys.platform.startswith('os2'):  # pragma: no cover
        cmd = ['open']
    elif sys.platform.startswith('linux'):
        cmd = ['xdg-open']
    elif sys.platform.startswith('win'):  # pragma: no cover
        cmd = []
    else:  # pragma: no cover
        print(lang.fname)
        return
    cmd.append(lang.fname.as_posix())
    subprocess.call(cmd)


@command()
@assert_repos
def create(args):
    """Create a new languoid directory for a languoid specified by name and level.

    glottolog --repos=. create <parent> <name> <level>
    """
    assert args.args[2] in ['family', 'language', 'dialect']
    parent = args.repos.languoid(args.args[0]) or None
    outdir = parent.dir if parent else args.repos.tree
    lang = Languoid.from_name_id_level(
        outdir,
        args.args[1],
        args.repos.glottocodes.new(args.args[1]),
        args.args[2],
        **dict(prop.split('=') for prop in args.args[3:]))

    print("Info written to %s" % lang.write_info(outdir=outdir))


@command()
@assert_repos
def bib(args):
    """Compile the monster bibfile from the BibTeX files listed in references/BIBFILES.ini

    glottolog bib [rebuild]
    """
    compile(args.repos, args.log, rebuild=bool(args.args))


@command()
@assert_repos
def tree(args):
    """Print the classification tree starting at a specific languoid.

    glottolog --repos=. tree <GLOTTOCODE>|<ISO-CODE> [MAXLEVEL]

    MAXLEVEL [family|language|dialect] will limit the displayed children.
    """
    start = existing_lang(args)
    maxlevel = None
    if len(args.args) > 1:
        try:
            maxlevel = int(args.args[1])
        except Exception:
            maxlevel = args.repos.languoid_levels[args.args[1]] \
                if args.args[1] in args.repos.languoid_levels else None
    args.repos.ascii_tree(start, maxlevel=maxlevel)


@command(usage="""
Print the classification tree starting at a specific languoid in Newick format.

    glottolog --repos=. newick [--template="{{l.id}}"] [<GLOTTOCODE>|<ISO-CODE>]

The --template option can be used to control the node labels in the Newick string.
Values for this option must be valid python format strings expecting a single
template variable `l` which points to the Languoid instance.
In addition to Languoid attributes and properties specified as "{{l.<attr>}}",
e.g. "{{l.id}}" for the Glottocode of a Languoid, the following custom format specs
can be used:
{0}""".format(
    '\n'.join('    l:{0}\t{1[1]}'.format(k, v) for k, v in Languoid._format_specs.items())))
@assert_repos
def newick(args):
    parser = argparse.ArgumentParser(prog='newick')
    parser.add_argument('root', nargs='?', default=None, help='root node')
    parser.add_argument('--template', help='node label template', default=None)
    xargs = parser.parse_args(args.args)
    if xargs.root and not args.repos.languoid(xargs.root):
        raise ParserError('Invalid root node {0}'.format(xargs.root))
    sprint(args.repos.newick_tree(xargs.root, template=xargs.template))


@command()
@assert_repos
def index(args):
    """Create an index page listing and linking to all languoids of a specified level.

    glottolog index (family|language|dialect|all)
    """
    def make_index(level, languoids, repos):
        fname = dict(
            language='languages', family='families', dialect='dialects')[level.name]
        links = defaultdict(dict)
        for lang in languoids:
            label = '{0.name} [{0.id}]'.format(lang)
            if lang.iso:
                label += '[%s]' % lang.iso
            links[slug(lang.name)[0]][label] = \
                lang.fname.relative_to(repos.languoids_path())

        with repos.languoids_path(fname + '.md').open('w', encoding='utf8') as fp:
            fp.write('## %s\n\n' % fname.capitalize())
            fp.write(' '.join(
                '[-%s-](%s_%s.md)' % (i.upper(), fname, i) for i in sorted(links.keys())))
            fp.write('\n')

        for i, langs in links.items():
            with repos.languoids_path(
                    '%s_%s.md' % (fname, i)).open('w', encoding='utf8') as fp:
                for label in sorted(langs.keys()):
                    fp.write('- [%s](%s)\n' % (label, langs[label]))

    langs = list(args.repos.languoids())
    for level in args.repos.languoid_levels.values():
        if not args.args or args.args[0] == level.name:
            make_index(level, [l for l in langs if l.level == level], args.repos)


@command()
@assert_repos
def check(args):
    """Check the glottolog data for consistency.

    glottolog check [tree|refs]
    """
    def error(obj, msg):
        args.log.error(message(obj, msg))

    def warn(obj, msg):
        args.log.warn(message(obj, msg))

    def info(obj, msg):
        args.log.info(message(obj, msg))

    what = args.args[0] if args.args else 'all'

    if what in ['all', 'refs']:
        for bibfile in args.repos.bibfiles:
            bibfile.check(args.log)

    if what not in ['all', 'tree']:
        return

    refkeys = set()
    for bibfile in args.repos.bibfiles:
        refkeys = refkeys.union(bibfile.keys())

    iso = args.repos.iso
    info(iso, 'checking ISO codes')
    info(args.repos, 'checking tree')
    by_level = Counter()
    by_category = Counter()
    iso_in_gl, languoids, iso_splits, hid = {}, {}, [], {}
    names = defaultdict(set)

    for attr in args.repos.__config__:
        for obj in getattr(args.repos, attr).values():
            ref_id = getattr(obj, 'reference_id', None)
            if ref_id and ref_id not in refkeys:
                error(obj, 'missing reference: {0}'.format(ref_id))

    for lang in args.repos.languoids():
        # duplicate glottocodes:
        if lang.id in languoids:
            error(
                lang.id,
                'duplicate glottocode\n{0}\n{1}'.format(languoids[lang.id].dir, lang.dir))
        languoids[lang.id] = lang

    for lang in languoids.values():
        ancestors = lang.ancestors_from_nodemap(languoids)
        children = lang.children_from_nodemap(languoids)

        if lang.latitude and not (-90 <= lang.latitude <= 90):
            error(lang, 'invalid latitude: {0}'.format(lang.latitude))
        if lang.longitude and not (-180 <= lang.longitude <= 180):
            error(lang, 'invalid longitude: {0}'.format(lang.longitude))

        assert isinstance(lang.countries, list)
        assert isinstance(lang.macroareas, list)

        if 'sources' in lang.cfg:
            for ref in Reference.from_list(lang.cfg.getlist('sources', 'glottolog')):
                if ref.key not in refkeys:
                    error(lang, 'missing source: {0}'.format(ref))

        for attr in ['classification_comment', 'ethnologue_comment']:
            obj = getattr(lang, attr)
            if obj:
                obj.check(lang, refkeys, args.log)

        names[lang.name].add(lang)
        by_level.update([lang.level.name])
        if lang.level == args.repos.languoid_levels.language:
            by_category.update([lang.category])

        if iso and lang.iso:
            if lang.iso not in iso:
                warn(lang, 'invalid ISO-639-3 code [%s]' % lang.iso)
            else:
                isocode = iso[lang.iso]
                if lang.iso in iso_in_gl:
                    error(
                        isocode,
                        'duplicate: {0}, {1}'.format(
                            iso_in_gl[lang.iso].id, lang.id))  # pragma: no cover
                iso_in_gl[lang.iso] = lang
                isocheck = pyglottolog.iso.check_lang(
                    args.repos, isocode, lang, iso_splits=iso_splits)
                if isocheck:
                    level, lang, msg = isocheck
                    dict(info=info, warn=warn)[level](lang, msg)

        if lang.hid is not None:
            if lang.hid in hid:
                error(
                    lang.hid,
                    'duplicate hid\n{0}\n{1}'.format(languoids[hid[lang.hid]].dir, lang.dir))
            else:
                hid[lang.hid] = lang.id

        if not lang.id.startswith('unun9') and lang.id not in args.repos.glottocodes:
            error(lang, 'unregistered glottocode')
        for attr in ['level', 'name']:
            if not getattr(lang, attr):
                error(lang, 'missing %s' % attr)  # pragma: no cover
        if lang.level == args.repos.languoid_levels.language:
            parent = ancestors[-1] if ancestors else None
            if parent and parent.level != args.repos.languoid_levels.family:  # pragma: no cover
                error(lang, 'invalid nesting of language under {0}'.format(parent.level))
            for child in children:
                if child.level != args.repos.languoid_levels.dialect:  # pragma: no cover
                    error(child,
                          'invalid nesting of {0} under language'.format(child.level))
        elif lang.level == args.repos.languoid_levels.family:
            for d in lang.dir.iterdir():
                if d.is_dir():
                    break
            else:
                error(lang, 'family without children')  # pragma: no cover

    if iso:
        for level, obj, msg in pyglottolog.iso.check_coverage(iso, iso_in_gl, iso_splits):
            dict(info=info, warn=warn)[level](obj, msg)  # pragma: no cover

    bookkeeping_gc = args.repos.language_types.bookkeeping.pseudo_family_id
    for name, gcs in sorted(names.items()):
        if len(gcs) > 1:
            # duplicate names:
            method = error
            if len([1 for n in gcs if n.level != args.repos.languoid_levels.dialect]) <= 1:
                # at most one of the languoids is not a dialect, just warn
                method = warn  # pragma: no cover
            if len([1 for n in gcs
                    if (not n.lineage) or (n.lineage[0][1] != bookkeeping_gc)]) <= 1:
                # at most one of the languoids is not in bookkeping, just warn
                method = warn  # pragma: no cover
            method(name, 'duplicate name: {0}'.format(', '.join(sorted(
                ['{0} <{1}>'.format(n.id, n.level.name[0]) for n in gcs]))))

    def log_counter(counter, name):
        msg = [name + ':']
        maxl = max([len(k) for k in counter.keys()]) + 1
        for k, l in counter.most_common():
            msg.append(('{0:<%s} {1:>8,}' % maxl).format(k + ':', l))
        msg.append(('{0:<%s} {1:>8,}' % maxl).format('', sum(list(counter.values()))))
        print('\n'.join(msg))

    log_counter(by_level, 'Languoids by level')
    log_counter(by_category, 'Languages by category')
    return by_level


@command()
@assert_repos
def metadata(args):
    """List all metadata fields used in languoid INI files and their frequency.

    glottolog metadata
    """
    ops = defaultdict(Counter)

    for l in args.repos.languoids():
        for secname, sec in l.cfg.items():
            ops[secname].update(opt for opt, val in sec.items() if val)

    ops.pop('DEFAULT', None)

    t = Table('section', 'option', 'count')
    for section, options in ops.items():
        t.append([section, '', float(sum(options.values()))])
        for k, n in options.most_common():
            t.append(['', k, float(n)])
    print(t.render(condensed=False, floatfmt=',.0f'))


@command()
@assert_repos
def refsearch(args):
    """Search Glottolog references

    glottolog --repos=. refsearch "QUERY"

    E.g.:
    - glottolog refsearch "Izi provider:hh"
    - glottolog refsearch "author:Haspelmath provider:wals"
    """
    count, results = fts.search(args.repos, args.args[0])
    table = Table('ID', 'Author', 'Year', 'Title')
    for res in results:
        table.append([res.id, res.author, res.year, res.title])
    sprint(table.render(tablefmt='simple'))
    print('({} matches)'.format(count))


@command()
@assert_repos
def refindex(args):
    """Index all bib files for use with `glottolog refsearch`.

    glottolog --repos=. refindex

    This will take about 15 minutes and create an index of about 450 MB.
    """
    return fts.build_index(args.repos, args.log)


@command()
@assert_repos
def langsearch(args):
    """Search Glottolog languoids

    glottolog --repos=. langsearch "QUERY"
    """
    def highlight(text):
        res, i = '', 0
        for m in re.finditer('\[\[(?P<m>[^\]]+)\]\]', text):
            res += text[i:m.start()]
            res += colored(m.group('m'), 'red', attrs=['bold'])
            i = m.end()
        res += text[i:]
        return res + '\n'

    count, results = fts.search_langs(args.repos, args.args[0])
    cwd = os.getcwd()
    print('{} matches'.format(count))
    for res in results:
        try:
            p = Path(res.fname).relative_to(Path(cwd))
        except ValueError:
            p = res.fname
        sprint('{0.name} [{0.id}] {0.level}'.format(res), color=None, attrs=['bold'])
        sprint(p, color='green')
        sprint(highlight(res.highlights) if res.highlights else '')
    print('{} matches'.format(count))


@command()
@assert_repos
def langindex(args):
    """Index all bib files for use with `glottolog langsearch`.

    glottolog --repos=. langindex

    This will take a couple of minutes and create an index of about 60 MB.
    """
    return fts.build_langs_index(args.repos, args.log)


@command()
@assert_repos
def update_sources(args):
    """Update the [sources] section in languoid info files according to `lgcode` fields in bibfiles.
    """
    langs = args.repos.languoids_by_code()
    updated = []
    sources = defaultdict(set)
    for bib in args.repos.bibfiles:
        for entry in bib.iterentries():
            for lang in entry.languoids(langs)[0]:
                sources[lang.id].add('{0}:{1}'.format(bib.id, entry.key))

    for gc, refs in sources.items():
        if refs != set(r.key for r in langs[gc].sources):
            langs[gc].sources = [Reference(key=ref) for ref in sorted(refs)]
            langs[gc].write_info()
            updated.append(gc)
    print('{0} languoids updated'.format(len(updated)))


@command()
@assert_repos
def tree2lff(args):
    """Create lff.txt and dff.txt from the current languoid tree.

    glottolog tree2lff
    """
    lff.tree2lff(args.repos, args.log)


@command()
@assert_repos
def lff2tree(args):
    """Recreate tree from lff.txt and dff.txt

    glottolog lff2tree [test]
    """
    try:
        lff.lff2tree(args.repos, args.log)
    except ValueError:  # pragma: no cover
        print("""
Something went wrong! Roll back inconsistent state running

    rm -rf languoids
    git checkout languoids
""")
        raise

    if args.args and args.args[0] == 'test':  # pragma: no cover
        print("""
You can run

    diff -rbB build/tree/ languoids/tree/

to inspect the changes in the directory tree.
""")
    else:
        print("""
Run

    git status

to inspect changes in the directory tree.
You can run

    diff -rbB build/tree/ languoids/tree/

to inspect the changes in detail.

- To discard changes run

    git checkout languoids/tree

- To commit and push changes, run

    git add -A languoids/tree/...

  for any newly created nodes listed under

# Untracked files:
#   (use "git add <file>..." to include in what will be committed)
#
#	languoids/tree/...

  followed by

    git commit -a -m"reason for change of classification"
    git push origin
""")
