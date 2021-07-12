# pyglottolog

Programmatic access to [Glottolog data](https://github.com/glottolog/glottolog).

[![Build Status](https://github.com/glottolog/pyglottolog/workflows/tests/badge.svg?branch=master)](https://github.com/glottolog/pyglottolog/actions?query=workflow%3Atests+branch%3Amaster)
[![codecov](https://codecov.io/gh/glottolog/pyglottolog/branch/master/graph/badge.svg)](https://codecov.io/gh/glottolog/pyglottolog)
[![Documentation Status](https://readthedocs.org/projects/pyglottolog/badge/?version=latest)](https://pyglottolog.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/pyglottolog.svg)](https://pypi.org/project/pyglottolog)


## Install

To install `pyglottolog` you need a python installation on your system, running python >3.6. Run
```shell script
pip install pyglottolog
```

This will also install the command line interface `glottolog`.

**Note:** To make use of `pyglottolog` you also need a local copy of the
[Glottolog data](https://github.com/glottolog/glottolog). This can be
- a clone of the [glottolog/glottolog](https://github.com/glottolog/glottolog) repository or your fork of it,
- an unzipped [released version of Glottolog](https://github.com/glottolog/glottolog/releases) from GitHub,
- or an unzipped download of a [released version of Glottolog](https://doi.org/10.5281/zenodo.596479) from ZENODO.

Make sure you remember where this local copy of the data is located - you may
have to pass this location as option when using `pyglottolog`.

A convenient way to clone the data repository, keep it updated and access it
from `pyglottolog` is provided
by [`cldfbench`](https://pypi.org/project/cldfbench). See the [`README`](https://github.com/cldf/cldfbench#catalogs) for details.


## Python API

Using `pyglottolog`, Glottolog data can be accessed programmatically from within python programs.
All functionality is mediated through an instance of `pyglottolog.Glottolog`, e.g.
```python
>>> from pyglottolog import Glottolog
>>> glottolog = Glottolog('.')
>>> print(glottolog)
<Glottolog repos v0.2-259-g27ac0ef at /.../glottolog>
```

For details, refer to the [API documentation at readthedocs](https://pyglottolog.readthedocs.io/en/latest/index.html).


## Command line interface

Command line functionality is implemented via sub-commands of `glottolog`. The list of
available sub-commands can be inspected running
```shell script
$ glottolog -h
usage: glottolog [-h] [--log-level LOG_LEVEL] [--repos REPOS]
                 [--repos-version REPOS_VERSION]
                 COMMAND ...

optional arguments:
  -h, --help            show this help message and exit
  --log-level LOG_LEVEL
                        log level [ERROR|WARN|INFO|DEBUG] (default: 20)
  --repos REPOS         clone of glottolog/glottolog
  --repos-version REPOS_VERSION
                        version of repository data. Requires a git clone!
                        (default: None)

available commands:
  Run "COMAMND -h" to get help for a specific command.

  COMMAND
    cldf                Dump Glottolog data as CLDF dataset
    create              Create a new languoid directory for a languoid
                        specified by name and level.
    edit                Open a languoid's INI file in a text editor.
    htmlmap             Create an HTML/Javascript map (using leaflet) of
                        Glottolog languoids.
    iso2codes           Map ISO codes to the list of all Glottolog languages
                        and dialects subsumed "under" it.
    langdatastats       List all metadata fields used in languoid INI files
                        and their frequency.
    langsearch          Search Glottolog languoids.
    languoids           Write languoids data to csv files
    refsearch           Search Glottolog references
    searchindex         Index
    show                Display details of a Glottolog object.
    tree                Print the classification tree starting at a specific
                        languoid.
```


### Extracting languoid data

Glottolog data is often integrated with other data or incorporated as reference
data in tools, e.g. as [LanguageTable](https://github.com/cldf/cldf/tree/master/components/languages)
in a [CLDF](https://cldf.clld.org) dataset.

To do this, the LanguageTable from [glottolog/glottolog-cldf](https://github.com/glottolog/glottolog-cldf)
could be copied, or one may use `glottolog`'s `languoids` subcommand, which
dumps basic languoid data into a CSVW file with accompanying metadata:

```shell script
glottolog languoids [--output=OUTDIR] [--version=VERSION]
```

This will create a CSVW package, i.e. 
- a CSV table `glottolog-languoids-VERSION.csv`
- and a JSON description `glottolog-languoids-VERSION.csv-metadata.json`

where `VERSION` is the result of running `git describe` on the data repository,
or the version string passed as`--version=VERSION` in case you are running the command
on an export of the repository or a download from ZENODO.


### Languoid search

To allow convenient search across all languoid info files, `pyglottolog` comes with functionality
to create and search a [Whoosh](https://whoosh.readthedocs.io/en/latest/intro.html) index. To do
so, run
```shell script
glottolog searchindex
```

This will take a couple of minutes (~15 on a somewhat beefy laptop with SSD) and build an index of 
about 800 MB size at `build/`.

Now you can search the index, e.g. using alternative names as query:
```shell
$ glottolog langsearch "Abipónok"
1 matches
Abipon [abip1241] language
languoids/tree/guai1249/guai1250/abip1241/md.ini
Abipónok [hu]

1 matches
```

But you can also exploit the schema defined in 
[pyglottolog.fts.get_langs_index](https://github.com/glottolog/pyglottolog/blob/c382b849b5245acba78d8022aadd4de83e73e909/src/pyglottolog/fts.py#L41-L52);
i.e. use fields in [your query](https://whoosh.readthedocs.io/en/latest/querylang.html):
```shell
$ glottolog langsearch "country:PG"
...

Alamblak [alam1246] language
languoids/tree/sepi1257/sepi1258/east2496/alam1246/md.ini
Papua New Guinea (PG)

906 matches

$ glottolog --repos=. langsearch "iso:mal"
...

Malayalam [mala1464] language
languoids/tree/drav1251/sout3133/sout3138/tami1291/tami1292/tami1293/tami1294/tami1297/tami1298/mala1541/mala1464/md.ini

1 matches
```


### Reference search

The same can be done for reference data: To create a Whoosh index with all reference data, run
```shell script
glottolog searchindex
```

Now you can query the index (using the fields described in
[the schema](https://github.com/glottolog/pyglottolog/blob/c382b849b5245acba78d8022aadd4de83e73e909/src/pyglottolog/fts.py#L118-L128)):
```shell
$ glottolog refsearch "author:Haspelmath AND title:Atlas"
...
(13 matches)
```
