from subprocess import check_output
from collections import Counter

from clldutils.markup import Table

URL = 'https://github.com/lingpy/bibliography/raw/master/evobib-converted.bib'


def bibtool(bib):  # pragma: no cover
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
        args.append('--{0}="{1}"'.format(k, v))
    args.append(bib.name)
    res = check_output(args, cwd=str(bib.parent))
    with bib.open(mode='wb') as fp:
        fp.write(res)


def update(newbib, bibfile, log):  # pragma: no cover
    bibtool(newbib)
    stats = Counter()

    def fix_entry_type(entry):
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

    bibfile.update(newbib, log=log)
    bibfile.visit(fix_entry_type)
    bibfile.check(log)
    res = Table('entry type', '#')
    res.extend(list(stats.most_common()))
    res.append(['TOTAL', sum(stats.values())])
    print('\n' + res.render(tablefmt='simple'))
