"""
Functionality to massage evobib into shape for Glottolog.
"""
import pathlib
import argparse
from subprocess import check_output
from collections import Counter, OrderedDict

from clldutils.clilib import Table

from pyglottolog import latex

latex.register()


def bibtool(bib: pathlib.Path):  # pragma: no cover
    """Run bibtool to normalize the BibTeX."""
    args = ['bibtool', '-R']
    for k, v in [
        ('print.align.key', '0'),
        ('preserve.key.case', 'on'),
        ('print.line.length', '10000'),
        ('select.crossrefs', 'on'),
        ('expand.crossref', 'on'),
        ('new.entry.type', 'mvreference'),
        ('new.entry.type', 'mvbook'),
        ('new.entry.type', 'bookinbook'),
        ('new.entry.type', 'thesis'),
        ('new.entry.type', 'report'),
    ]:
        args.append(f'--{k}="{v}"')
    args.append(bib.name)
    res = check_output(args, cwd=str(bib.parent))
    with bib.open(mode='wb') as fp:
        fp.write(res)


def update(newbib, bibfile, log):  # pragma: no cover
    """Update the bib provider version from the upstream curated file."""
    bibtool(newbib)
    stats = Counter()

    def fix_entry_type(entry):
        """We translate some biblatex entry types."""
        type_ = entry.type.lower()
        type_map = {
            'thesis': 'phdthesis',
            'mvreference': 'misc',
            'mvbook': 'book',
            'bookinbook': 'book',
            'report': 'techreport',
        }
        entry.type = type_map.get(type_, type_)
        stats.update([entry.type])

    def unescape(s):
        s = s.replace(r'\%', '||||')
        s = s.encode('utf8').decode('latex+utf8')
        return s.replace('||||', '%')

    def unescape_latex(entry):
        entry.fields = OrderedDict(
            [(k, v if k in ['url'] else unescape(v)) for k, v in entry.fields.items()])

    bibfile.update(newbib, log=log)
    bibfile.visit(fix_entry_type)
    bibfile.visit(unescape_latex)
    bibfile.check_lang(log)
    with Table(argparse.Namespace(format='simple'), 'entry type', '#') as t:
        t.extend(list(stats.most_common()))
        t.append(['TOTAL', sum(stats.values())])
