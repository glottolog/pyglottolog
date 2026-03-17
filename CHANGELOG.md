# Changes


## [4.0.0] - unreleased

- Drop py3.8 compat
- Remove dependency on `attrs`
- Remove fts search functionality built on `whoosh`.

### Backwards incompatibility

- Removed legacy import locations.
- Removed "languoids" command. Since the Glottolog data is now available as CLDF dataset, a single
  CSVW table with the languoid metadata is not needed anymore.
