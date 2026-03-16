# pyglottolog

Programmatic access to [Glottolog data](https://github.com/glottolog/glottolog).

[![Build Status](https://github.com/glottolog/pyglottolog/workflows/tests/badge.svg?branch=master)](https://github.com/glottolog/pyglottolog/actions?query=workflow%3Atests)
[![Documentation Status](https://readthedocs.org/projects/pyglottolog/badge/?version=latest)](https://pyglottolog.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/pyglottolog.svg)](https://pypi.org/project/pyglottolog)

> [!NOTE]  
> Accessing Glottolog data programmatically has become a lot easier with the
> [Glottolog CLDF dataset](https://github.com/glottolog/glottolog-cldf). Thus, `pyglottolog` now
> mostly serves as internal data curation tool.


## Install

To install `pyglottolog` you need a python installation on your system, running python >3.8. Run
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
    create              Create a new languoid directory for a languoid
                        specified by name and level.
    edit                Open a languoid's INI file in a text editor.
    htmlmap             Create an HTML/Javascript map (using leaflet) of
                        Glottolog languoids.
    iso2codes           Map ISO codes to the list of all Glottolog languages
                        and dialects subsumed "under" it.
    langdatastats       List all metadata fields used in languoid INI files
                        and their frequency.
    languoids           Write languoids data to csv files
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
