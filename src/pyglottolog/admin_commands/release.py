"""
Write release info to .zenodo.json, CITATION.md and CONTRIBUTORS.md
"""
import shlex
import subprocess

import packaging.version

from pyglottolog.metadata import prepare_release


def register(parser):  # pylint: disable=C0116
    parser.add_argument('--version', help="version number without leading 'v'", default=None)


def run(args):  # pylint: disable=C0116
    try:  # pragma: no cover
        branch = ''
        out = subprocess.check_output(shlex.split(f"git -C {args.repos.repos} branch"))
        for line in out.decode('utf8').split('\n'):
            if line.startswith('*'):
                branch = line[1:].strip()
        assert branch.startswith('release')
    except subprocess.CalledProcessError:
        pass
    version = getattr(args.repos.publication.zenodo, 'version', args.version)
    assert not packaging.version.parse(version).is_prerelease, 'invalid release version number'
    print(prepare_release(args.repos, version=version))
