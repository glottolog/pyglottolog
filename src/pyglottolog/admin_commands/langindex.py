"""
Create an index pages listing and linking to all languoids of a specified level.
"""
import collections

from clldutils.misc import slug


def run(args):  # pylint: disable=C0116
    def make_index(level, languoids, repos):
        fname = dict(  # pylint: disable=R1735
            language='languages', family='families', dialect='dialects')[level.name]
        links = collections.defaultdict(dict)
        for lang in languoids:
            label = f'{lang.name} [{lang.id}]'
            if lang.iso:
                label += f'[{lang.iso}]'
            links[slug(lang.name)[0]][label] = \
                lang.fname.relative_to(repos.languoids_path())

        with repos.languoids_path(fname + '.md').open('w', encoding='utf8') as fp:
            fp.write(f'## {fname.capitalize()}\n\n')
            fp.write(' '.join(f'[-{i.upper()}-]({fname}_{i}.md)' for i in sorted(links.keys())))
            fp.write('\n')

        for i, langs in links.items():
            with repos.languoids_path(f'{fname}_{i}.md').open('w', encoding='utf8') as fp:
                for label in sorted(langs.keys()):
                    fp.write(f'- [{label}]({langs[label]})\n')

    langs = list(args.repos.languoids())
    for level in args.repos.languoid_levels.values():
        make_index(level, [lang for lang in langs if lang.level == level], args.repos)
