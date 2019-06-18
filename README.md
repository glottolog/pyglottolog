# pyglottolog

Programmatic access to [Glottolog data](https://github.com/glottolog/glottolog).

[![Build Status](https://travis-ci.org/clld/pyglottolog.svg?branch=master)](https://travis-ci.org/glottolog/pyglottolog)
[![codecov](https://codecov.io/gh/clld/pyglottolog/branch/master/graph/badge.svg)](https://codecov.io/gh/glottolog/pyglottolog)
[![PyPI](https://img.shields.io/pypi/v/pyglottolog.svg)](https://pypi.org/project/pyglottolog)


## Install

To install `pyglottolog` you need a python installation on your system, running python 2.7 or >3.4. Run
```
pip install pyglottolog
```

This will also install the command line interface `glottolog`.

**Note:** To make use of `pyglottolog` you also need a local copy of the
[Glottolog data](https://github.com/glottolog/glottolog). This can be
- a clone of the [glottolog/glottolog](https://github.com/clld/glottolog) repository or your fork of it,
- an unzipped [released version of Glottolog](https://github.com/glottolog/glottolog/releases) from GitHub,
- or an unzipped download of a [released version of Glottolog](https://doi.org/10.5281/zenodo.596479) from ZENODO.

Make sure you remember where this local copy of the data is located - you always
have to pass this location as argument when using `pyglottolog`.


## Python API

Using `pyglottolog`, Glottolog data can be accessed programmatically from within python programs.
All functionality is mediated through an instance of `pyglottolog.Glottolog`, e.g.
```python
>>> from pyglottolog import Glottolog
>>> glottolog = Glottolog('.')
>>> print(glottolog)
<Glottolog repos v0.2-259-g27ac0ef at /.../glottolog>
```

### Accessing languoid data

The data in languoid info files in the `languoids/tree` subdirectory is mainly accessed through
two methods:

```python
>>> glottolog.languoid('stan1295')
<Language stan1295>
>>> print(glottolog.languoid('stan1295'))
German [stan1295]
```

### Accessing reference data
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

### Performance considerations

Reading the data for Glottolog's almost 25,000 languoids from the same number of files in individual
directories isn't particularly quick. So on average computers running
```python
>>> list(Glottolog().languoids())
```
would take around 15 seconds.

Due to this, care should be taken not to read languoid data from disk repeatedly. In particular
"N+1"-type problems should be avoided, where one would read all languoid into memory and then look
up attributes on each languoid, thereby triggering new reads from disk. This may easily happen,
since attributes such as `Languoid.family` are implemented as
[properties](https://docs.python.org/3/howto/descriptor.html#properties), which traverse the
directory tree and read information from disk at **access** time.

To make it possible to avoid such problems, many of these properties can be substituted with a call
to a similar method of `Languoid`, which accepts a "node map" (i.e. a `dict` mapping `Languoid.id` 
to `Languoid` objects) as parameter, e.g. `Languoid.ancestors_from_nodemap` or
`Languoid.descendants_from_nodemap`. Typical usage would look as follows:
```python
>>> languoids = {l.id: l for l in Glottolog().languoids()}
>>> for l in languoids.values():
...    if not l.ancestors_from_nodemap(languoids):
...        print('top-level {0}: {1}'.format(l.level, l.name))
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

Note: The location of your local clone or export of the Glottolog data should
be passed as `--repos=PATH/TO/glottolog`.


### Extracting languoid data

Glottolog data is often integrated with other data or incorporated as reference
data in tools, e.g. as [LanguageTable](https://github.com/cldf/cldf/tree/master/components/languages)
in a [CLDF](https://cldf.clld.org) dataset.

To make this easier, `pyglottolog` provides the `languoids` subcommand, which
dumps basic languoid data into a CSVW file with accompanying metadata:

```bash
glottolog --repos=PATH/TO/glottolog languoids [--output=OUTDIR] [--version=VERSION]
```

This will create a CSVW package, i.e. 
- a CSV table `glottolog-languoids-VERSION.csv`
- and a JSON description `glottolog-languoids-VERSION.csv-metadata.json`

where `VERSION` is the result of running `git describe` on the data repository,
or the version string passed as`--version=VERSION` in case you are running the command
on an export of the repository or a download from ZENODO.