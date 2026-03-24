"""
Utilities used in Glottolog commands.
"""
import dataclasses
import pathlib
from typing import TYPE_CHECKING, Optional

from clldutils.clilib import ParserError, PathType
from clldutils.jsonlib import load, dump

from pyglottolog.util import message
from pyglottolog.languoids import Glottocode

if TYPE_CHECKING:  # pragma: no cover
    from pyglottolog.languoids import Languoid

__all__ = ['add_output_dir', 'get_languoid']


def add_output_dir(parser):
    """Add an option specifying an output directory."""
    parser.add_argument(
        '--output',
        help='An existing directory for the output',
        type=PathType(type='dir'),
        default=pathlib.Path('.'),
    )


def get_languoid(args, spec: str) -> Optional['Languoid']:
    """Get a languoid."""
    if spec:
        lang = args.repos.languoid(spec)
        if not lang:
            raise ParserError(f'Invalid languoid {spec}')
        return lang
    return None


@dataclasses.dataclass
class LanguoidStats:
    """Stores languoid stats and makes comparison simple."""
    language: list[Glottocode] = dataclasses.field(default_factory=list)
    family: list[Glottocode] = dataclasses.field(default_factory=list)
    dialect: list[Glottocode] = dataclasses.field(default_factory=list)

    __fname__ = 'languoids.json'

    @classmethod
    def from_json(cls, api):
        if api.build_path(cls.__fname__).exists():
            return cls(**load(api.build_path(cls.__fname__)))
        return cls()

    @classmethod
    def from_tree(cls, api):
        res = cls()
        for lang in api.languoids():
            res.update(lang)
        return res

    def update(self, lang):
        getattr(self, lang.level.name).append(lang.id)

    def to_json(self, api):
        dump(dataclasses.asdict(self), api.build_path(self.__fname__), indent=2)

    def check(self, languoids, log):
        """Compare stats with current status in repos."""
        current = LanguoidStats()
        for lang in languoids.values():
            current.update(lang)

        if self.language:
            for gc in set(self.language) - set(current.language):
                if gc not in languoids:
                    log.error(message(gc, 'deleted language level languoid!'))
                else:
                    log.warning(message(
                        gc, f'switched from language to {languoids[gc].level.name}'))

        for field in dataclasses.fields(self):
            old = set(getattr(self, field.name))
            new = set(getattr(current, field.name))

            if old and old != new:
                log.info(f'{field.name}: \t{len(old - new)} deleted,\t{len(new - old)} added')
