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

