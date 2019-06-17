# coding: utf8
"""
Modules implementing functionality to add links to resources for Glottolog languoids must
provide a function with the following signature:

def iterupdated(languoids)

accepting the list of all Glottolog `Languoid` objects and yielding the ones that have been
updated in the function.
"""
from __future__ import unicode_literals, print_function, division
