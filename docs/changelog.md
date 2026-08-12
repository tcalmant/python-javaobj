# Release Notes

## 0.6.1

:Release Date: 2026-08-12

- Fixed the reading of `LinkedHashMap` (issue #30). Its entries are written
  in the block data of the `HashMap` it extends, and its own `accessOrder`
  field right after them. `v1` read that block data a second time, which
  desynchronized the stream and broke every field read afterwards; `v3`
  looked for the entries under the `LinkedHashMap` level instead of the
  `HashMap` one, and silently returned an empty map.
- Fixed the reading of arrays referenced more than once in `v2`
  (issue #62). Arrays were given a reference handle but were never stored,
  so a reference to an array could not be resolved, and a reference found
  in an array field was read as a class description. Class descriptions are
  also stored before their annotations now, as `v3` already does, so that
  what is read in between can refer to them.
- Giving a transformer class instead of an instance to `load()` or
  `loads()` now raises a `TypeError` naming the transformer, instead of
  failing later inside the parser with a missing argument (issue #54).
- The package declares itself as typed: it ships the PEP 561 `py.typed`
  marker, so type checkers use its hints once it is installed.
- Fixed wrong type hints, and the problems they were hiding (issue #39):
  `_do_classdesc()` and `_read_content()` are declared as optional, which
  is what they return on `TC_NULL`; reading an object, a class or an array
  without a class description now reports a `ValueError` instead of
  crashing on a missing attribute; and the `_read_content()` method of the
  `IJavaStreamParser` interface raises `NotImplementedError`, like the
  other ones, instead of returning `None`. `mypy` runs in the CI, with its
  configuration in `pyproject.toml`. Describing the functions which have no
  hints yet, mostly in the beans and transformers of `v1` and `v2`, is left
  for a next release.
- Added tests for the `java.time` handlers of `v1`, which had none.

## 0.6.0

:Release Date: 2026-08-12

- Fixed the version number, which was declared inconsistently across the
  tree (`pyproject.toml` said `0.5.0` while most modules still said
  `0.4.4`): every module tuple, docstring field, `pyproject.toml` and
  `setup.py` now agree.
- Documented `javaobj.v3` more thoroughly in the README: automatic
  conversion of Java collections to Python types, how to catch
  `javaobj.v3.exceptions`, and the parser/writer logger names.
- Added a containerized test matrix (`run_tests.sh` /
  `run_tests_containers.sh`, podman by default, Docker in CI) so `ci-build.yml`
  covers every Python version this project declares as supported, including
  2.7 and 3.4-3.7, which `actions/setup-python` cannot install on a current
  runner.
- Fixed two Java test sources that failed to compile or run once
  `tests/java`'s Maven build became an actual CI gate instead of a
  best-effort, silently-ignored step: a misnamed public class and a
  duplicate class name in `SerializationExample.java`, and a Swing-based
  test that now skips itself when there is no display instead of failing.
- Switched the build backend from `hatchling` to `setuptools`, so releases
  ship a single universal `py2.py3-none-any` wheel: Python 2.7 users get a
  wheel install instead of always building from source.
- Added this changelog and a `publish.yml` release workflow (build, SLSA
  provenance attestation, CycloneDX SBOM, PyPI Trusted Publishing, GitHub
  release), modeled on the `jsonrpclib`/`ipopo` projects.
