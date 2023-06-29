"""

"""
import pathlib
import tempfile
import collections

from pycldf.cli_util import add_dataset, get_dataset


def register(parser):
    add_dataset(parser)


def run(args):
    cldf = get_dataset(args)
    sid2lid = collections.defaultdict(set)
    for val in cldf.iter_rows('ValueTable'):
        for sid in val['Source']:
            sid2lid[sid].add(val['Language_ID'])

    languages = {lng['ID']: lng for lng in cldf.iter_rows('LanguageTable')}

    def format_lid(lid):
        lang = languages[lid]
        res = lang['Name']
        if lang['Glottocode']:
            res += ' [{}]'.format(lang['Glottocode'])
        elif lang['ISO639P3code']:
            res += ' [{}]'.format(lang['ISO639P3code'])
        return res

    fname = pathlib.Path(tempfile.gettempdir()) / 'elcat.bib'
    with fname.open('w', encoding='utf8') as fp:
        for source in cldf.sources.items():
            if any('Personal Communication' in source.get(field, '')
                   for field in ['howpublished', 'title']):
                continue
            if len(sid2lid[source.id]) < 100:
                source['lgcode'] = '; '.join(format_lid(lid) for lid in sid2lid[source.id])
            fp.write(source.bibtex())

    bibfile = args.repos.bibfiles['elcat.bib']
    bibfile.update(fname, log=args.log)
    bibfile.check(args.log)
    fname.unlink()
