
Releasing pyglottolog
=====================

- Do platform test via tox:
  ```shell
  tox -r
  ```

- Make sure flake8 passes:
  ```shell
  flake8 src
  ```

- Make sure API docs can be built:
  ```shell
  cd docs
  make clean html
  cd ..
  ```

- Update the version number, by removing the trailing `.dev0` in:
  - `setup.py`
  - `src/pyglottolog/__init__.py`
  - `docs.conf.py`

- Create the release commit:
  ```shell
  git commit -a -m "release <VERSION>"
  ```

- Create a release tag:
  ```shell
  git tag -a v<VERSION> -m"<VERSION> release"
  ```

- Release to PyPI:
  ```shell
  python setup.py clean --all
  rm dist/*
  python setup.py sdist bdist_wheel
  twine upload dist/*
  ```

- Push to github:
  ```shell
  git push origin
  git push --tags
  ```

- Increment version number and append `.dev0` to the version number for the new development cycle:
  - `src/pyglottolog/__init__.py`
  - `setup.py`
  - `docs/conf.py`

- Commit/push the version change:
  ```shell
  git commit -a -m "bump version for development"
  git push origin
  ```
