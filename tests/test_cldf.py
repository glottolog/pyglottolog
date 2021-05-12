import logging
import collections

from pycldf import StructureDataset

from pyglottolog.cldf import cldf


def test_cldf(tmp_path, api):
    ds = StructureDataset.in_dir(tmp_path)
    cldf(ds, collections.defaultdict(list), api, logging.getLogger(__name__))
