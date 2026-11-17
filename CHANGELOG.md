# Changes

## [5.0.0] - 2026-11-17

- Drop py3.9 and py3.10 compat
- Migrate to pyproject.toml
- SQLAlchemy 2.x compat

While nothing really changed with regards to functionality, we still release this as new major
version in order to make 4.x available for fixes in SQLAlchemy 1.4.x environments, while the 5.x
line will support SQLAlchemy 2.x exclusively.


## [4.0.1] - 2026-05-14

- Fixed computation of page numbers to also handle cases like "3+5+6".


## [4.0.0] - 2026-05-05

- Drop py3.8 compat
- Remove dependency on `attrs`
- Remove fts search functionality built on `whoosh`.

### Backwards incompatibility

- Removed legacy import locations.
- Removed "languoids" command. Since the Glottolog data is now available as CLDF dataset, a single
  CSVW table with the languoid metadata is not needed anymore.
