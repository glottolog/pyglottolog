"""
Modules implementing functionality to add links to resources for Glottolog languoids must
subclass util.LinkProvider and override `iterupdated`, a method with the following signature:

    def iterupdated(self, languoids)

accepting the list of all Glottolog `Languoid` objects and yielding the ones that have been
updated in the function.
"""
from os.path import dirname, basename, isfile, join
import glob

modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
