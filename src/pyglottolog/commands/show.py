"""
Display details of a Glottolog object.
"""
from pyglottolog.languoids import Reference
from pyglottolog.cli_util import get_languoid
from pyglottolog.util import sprint


def register(parser):
    parser.add_argument(
        'object',
        metavar='<GLOTTOCODE>|<ISO-CODE>|<BIBTEXKEY>',
    )


def run(args):
    if ':' in args.object:
        if args.object.startswith('**'):
            ref = Reference.from_string(args.object)
        else:
            ref = Reference(key=args.object)
        sprint('Glottolog reference {0}'.format(ref), attrs=['bold', 'underline'])
        print()
        src = ref.get_source(args.repos)
        sprint(src.text())
        print()
        sprint(src)
        return

    lang = get_languoid(args, args.object)
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
