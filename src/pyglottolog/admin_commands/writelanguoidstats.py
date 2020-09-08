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
try:
    from git import Repo
except ImportError:
    Repo = None

from clldutils import jsonlib


def run(args):
    if Repo:
        assert str(Repo(str(args.repos.repos)).active_branch) == 'master', \
            'Command should be run on master branch'
    res = {'language': [], 'family': [], 'dialect': []}
    for l in args.repos.languoids():
        res[l.level.name].append(l.id)
    jsonlib.dump(res, args.repos.build_path('languoids.json'))
