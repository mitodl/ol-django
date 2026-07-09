.. A new scriv changelog fragment.
..
.. Uncomment the section that is right (remove the leading dots).
.. For top level release notes, leave all the headers commented out.
..
Fixed
-----

- ``sync_object_property`` no longer attempts to update properties with a read-only definition (e.g. properties created with ``hasUniqueValue=True``), which previously raised a 400 ``PROPERTY_INVALID`` error from Hubspot on re-runs.
