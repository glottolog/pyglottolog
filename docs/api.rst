`pyglottolog.Glottolog`
=======================

Most of the Glottolog's data can be accessed through an instance of :class:`pyglottolog.Glottolog`.


.. autoclass:: pyglottolog.Glottolog
    :members: repos, tree, ftsindex, references_path, languoids_path, iso


Accessing configuration data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration data in `<https://github.com/glottolog/glottolog/tree/master/config>`_
can be accessed conveniently via the following properties of
:class:`pyglottolog.Glottolog`:


.. autoproperty:: pyglottolog.Glottolog.aes_status

.. autoproperty:: pyglottolog.Glottolog.aes_sources

.. autoproperty:: pyglottolog.Glottolog.document_types

.. autoproperty:: pyglottolog.Glottolog.med_types

.. autoproperty:: pyglottolog.Glottolog.macroareas

.. autoproperty:: pyglottolog.Glottolog.language_types

.. autoproperty:: pyglottolog.Glottolog.languoid_levels

.. autoproperty:: pyglottolog.Glottolog.editors

.. autoproperty:: pyglottolog.Glottolog.publication

See :doc:`configuration data <config>` for details about the returned
objects.



Accessing languoid data
~~~~~~~~~~~~~~~~~~~~~~~

.. autoproperty:: pyglottolog.Glottolog.glottocodes

.. automethod:: pyglottolog.Glottolog.languoid

.. automethod:: pyglottolog.Glottolog.languoids

.. automethod:: pyglottolog.Glottolog.languoids_by_code


The classification can be accessed via a :class:`pyglottolog.languoids.Languoid`'s
attributes. In addition, it can be visualized via

.. automethod:: pyglottolog.Glottolog.ascii_tree

and serialized as Newick string via

.. automethod:: pyglottolog.Glottolog.newick_tree


Accessing reference data
~~~~~~~~~~~~~~~~~~~~~~~~

.. autoproperty:: pyglottolog.Glottolog.bibfiles


Performance considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

Reading the data for Glottolog's more than 25,000 languoids from the same number of files in individual
directories isn't particularly quick. So on average computers running

.. code-block:: python

    >>> list(glottolog.languoids())


would take around 15 seconds.

Due to this, care should be taken not to read languoid data from disk repeatedly. In particular
"N+1"-type problems should be avoided, where one would read all languoids into memory and then look
up attributes on each languoid, thereby triggering new reads from disk. This may easily happen,
since attributes such as `Languoid.family` are implemented as
`properties <https://docs.python.org/3/howto/descriptor.html#properties>`_, which traverse the
directory tree and read information from disk at **access** time.

To make it possible to avoid such problems, many of these properties can be substituted with a call
to a similar method of `Languoid`, which accepts a "node map" (i.e. a `dict` mapping `Languoid.id` 
to `Languoid` objects) as parameter, e.g. `Languoid.ancestors_from_nodemap` or
`Languoid.descendants_from_nodemap`. Typical usage would look as follows:

.. code-block:: python

    >>> languoids = {l.id: l for l in glottolog.languoids()}
    >>> for l in languoids.values():
    ...    if not l.ancestors_from_nodemap(languoids):
    ...        print('top-level {0}: {1}'.format(l.level, l.name))

Alternatively, if you only want to **read** Glottolog data, you may enable caching
when instantiating :class:`pyglottolog.Glottolog`.

