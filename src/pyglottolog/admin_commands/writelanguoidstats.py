"""
Write simple languoid stats to build/languoids.json.

This is to allow comparison between two branches of the repos.

Intended usage:
```
git checkout master
glottolog-admin writelanguoidstats
git checkout <OTHER_BRANCH>
glottolog-admin check --old-languoids
```
"""
from clldutils import jsonlib


def run(args):  # pragma: no cover
    res = {'language': [], 'family': [], 'dialect': []}
    for lang in args.repos.languoids():
        res[lang.level.name].append(lang.id)
    jsonlib.dump(res, args.repos.build_path('languoids.json'))
