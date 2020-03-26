"""
Add missing macroareas for dialects.

By default, dialects are assumed to share the macroarea of their language.
"""


def run(args):
    langs = {l.id: l for l in args.repos.languoids()}
    updated = []

    for dialect in langs.values():
        if dialect.level == args.repos.languoid_levels['dialect'] and not dialect.macroareas:
            for _, lid, _ in reversed(dialect.lineage):
                language = langs[lid]
                if language.level == args.repos.languoid_levels['language']:
                    break
            else:  # pragma: no cover
                raise ValueError()
            dialect.macroareas = [ma for ma in language.macroareas]
            updated.append(dialect)

    for l in updated:
        l.write_info()

    print('{} dialects updated'.format(len(updated)))
