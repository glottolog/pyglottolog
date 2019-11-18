"""
Recreate tree from lff.txt and dff.txt
"""
from pyglottolog import lff


def run(args):
    try:
        lff.lff2tree(args.repos, args.log)
    except ValueError:  # pragma: no cover
        print("""
Something went wrong! Roll back inconsistent state running

    rm -rf languoids
    git checkout languoids
""")
        raise

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
