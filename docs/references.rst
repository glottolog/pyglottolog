Reference data
==============

Glottolog's `reference data <https://github.com/glottolog/glottolog/tree/master/references>`_ consists of bibliographical information in a set of BibTeX files, described
with metadata in
`BIBFILES.ini <https://github.com/glottolog/glottolog/blob/master/references/BIBFILES.ini>`_.

This information can be accessed via an instance of
:class:`pyglottolog.Glottolog`, too:

.. code-block:: python

    >>> Glottolog()
    >>> print(g.bibfiles['hh'].description)
    The bibliography of HH, typed in between 2005-2020.
    It has been annotated by hand (type and language).
    It contains descriptive material from all over the world, mostly lesser-known languages.
    >>> print(g.bibfiles['hh:s:Karang:Tati-Harzani'])
    @book{s:Karang:Tati-Harzani,
        author = {'Abd-al-'Ali Kārang},
        title = {Tāti va Harzani, do lahja az zabān-i bāstān-e Āẕarbāyjān},
        publisher = {Tabriz: Tabriz University Press},
        address = {Tabriz},
        pages = {6+160},
        year = {1334 [1953]},
        glottolog_ref_id = {41999},
        hhtype = {grammar_sketch},
        inlg = {Farsi [pes]},
        lgcode = {Tati, Harzani [hrz]},
        macro_area = {Eurasia}
    }

The objects representing reference data are described below.


.. autoclass:: pyglottolog.references.BibFiles
    :members:
    :special-members: __getitem__

.. autoclass:: pyglottolog.references.BibFile
    :members:
    :special-members: __getitem__, __str__

.. autoclass:: pyglottolog.references.Entry
    :members:

