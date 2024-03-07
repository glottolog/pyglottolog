"""
Write release info to .zenodo.json, CITATION.md and CONTRIBUTORS.md
"""
import shlex
import subprocess

import packaging.version

from pyglottolog.metadata import prepare_release


def register(parser):
    parser.add_argument('--version', help="version number without leading 'v'", default=None)


def run(args):
    try:
        branch = ''
        out = subprocess.check_output(shlex.split("git -C {} branch".format(args.repos.repos)))
        for line in out.decode('utf8').split('\n'):
            if line.startswith('*'):
                branch = line[1:].strip()
        assert branch.startswith('release')
    except subprocess.CalledProcessError:
        pass
    version = getattr(args.repos.publication.zenodo, 'version', args.version)
    assert not packaging.version.parse(version).is_prerelease, 'invalid release version number'
    print(prepare_release(args.repos, version=version))
