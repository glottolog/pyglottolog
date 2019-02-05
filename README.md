# pyglottolog

Programmatic access to [Glottolog data](https://github.com/clld/glottolog).

[![Build Status](https://travis-ci.org/clld/pyglottolog.svg?branch=master)](https://travis-ci.org/clld/pyglottolog)
[![codecov](https://codecov.io/gh/clld/pyglottolog/branch/master/graph/badge.svg)](https://codecov.io/gh/clld/pyglottolog)
[![PyPI](https://img.shields.io/pypi/v/pyglottolog.svg)](https://pypi.org/project/pyglottolog)


### Install

To install `pyglottolog` you need a python installation on your system, running python 2.7 or >3.4. Run
```
pip install pyglottolog
```

This will also install the command line interface `glottolog`.

**Note:** To make use of `pyglottolog` you also need a local copy of the
[Glottolog data](https://github.com/clld/glottolog). This can be
- a clone of the [clld/glottolog](https://github.com/clld/glottolog) repository or your fork of it,
- an unzipped [released version of Glottolog](https://github.com/clld/glottolog/releases) from GitHub,
- or an unzipped download of a [released version of Glottolog](https://doi.org/10.5281/zenodo.596479) from ZENODO.

Make sure you remember where this local copy of the data is located - you always
have to pass this location as argument when using `pyglottolog`.
  

## Python API

Glottolog data can also be accessed programmatically from within python programs.
All functionality is mediated through an instance of `pyglottolog.api.Glottolog`, e.g.
```python
>>> from pyglottolog.api import Glottolog
>>> api = Glottolog('.')
>>> print(api)
<Glottolog repos v0.2-259-g27ac0ef at /.../glottolog>
```

#### Accessing languoid data
```python
>>> api.languoid('stan1295')
<Language stan1295>
>>> print(api.languoid('stan1295'))
German [stan1295]
```

#### Accessing reference data
```python
>>> print(api.bibfiles['hh.bib']['s:Karang:Tati-Harzani'])
@book{s:Karang:Tati-Harzani,
    author = {'Abd-al-'Ali Kārang},
    title = {Tāti va Harzani},
    publisher = {Tabriz: Tabriz University Press},
    address = {Tabriz},
    pages = {6+160},
    year = {1334 [1953]},
    glottolog_ref_id = {41999},
    hhtype = {grammar_sketch},
    inlg = {Farsi [pes]},
    lgcode = {Harzani [hrz]},
    macro_area = {Eurasia}
}
```


## Command line interface

Command line functionality is implemented via sub-commands of `glottolog`. The list of
available sub-commands can be inspected running
```
$ glottolog --help
usage: glottolog [-h] [--verbosity VERBOSITY] [--log-level LOG_LEVEL]
                 [--repos REPOS]
                 command ...

Main command line interface of the pyglottolog package.

positional arguments:
  command               isobib | show | edit | create | bib | tree | newick |
                        index | check | metadata | refsearch | refindex |
                        langsearch | langindex | tree2lff | lff2tree
  args

optional arguments:
  -h, --help            show this help message and exit
  --verbosity VERBOSITY
                        increase output verbosity
  --log-level LOG_LEVEL
                        log level [ERROR|WARN|INFO|DEBUG]
  --repos REPOS         path to glottolog data repository

Use 'glottolog help <cmd>' to get help about individual commands.
```


