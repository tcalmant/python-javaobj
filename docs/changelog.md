# Release Notes

## 0.6.0

:Release Date: Unreleased

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
