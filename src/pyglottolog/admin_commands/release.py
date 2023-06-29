"""
Write release info to .zenodo.json, CITATION.md and CONTRIBUTORS.md
"""
import git.exc
import packaging.version

from git import Repo

from pyglottolog.metadata import prepare_release


def register(parser):
    parser.add_argument('--version', help="version number without leading 'v'", default=None)


def run(args):
    try:
        assert Repo(str(args.repos.repos)).active_branch.name.startswith('release')
    except git.exc.InvalidGitRepositoryError:
        pass
    version = getattr(args.repos.publication.zenodo, 'version', args.version)
    assert not packaging.version.parse(version).is_prerelease, 'invalid release version number'
    print(prepare_release(args.repos, version=version))
