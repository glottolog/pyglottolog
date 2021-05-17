
Configuration data
------------------

The `config <https://github.com/glottolog/glottolog/tree/master/config>`_ subdirectory of Glottolog data contains machine readable metadata like the list
of macroareas. This information can be accessed via an instance of 
:class:`pyglottolog.Glottolog`, too, using the stem of the filename as attribute name:

.. code-block:: python

    >>> for ma in Glottolog().macroareas.values():
    ...     print(ma.name)
    ...     
    South America
    Eurasia
    Africa
    Papunesia
    North America
    Australia

Below are the details of the API to access configuration data.


.. automodule:: pyglottolog.config
    :members:

