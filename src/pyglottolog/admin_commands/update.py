"""
Run all update commands in sequence.
"""
from pyglottolog.admin_commands import (
    isoretirements, langindex, updatelinks, updatemetadata, updatesources, updatemacroareas,
)


def run(args):  # pragma: no cover  # pylint: disable=C0116
    isoretirements.run(args)
    langindex.run(args)
    updatelinks.run(args)
    updatemetadata.run(args)
    updatesources.run(args)
    updatemacroareas.run(args)
