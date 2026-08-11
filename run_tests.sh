#!/bin/bash
#
# Runs the python-javaobj test suite for the current Python interpreter.
#
# Used both inside the per-version containers driven by
# run_tests_containers.sh, and directly in CI on the runner. javaobj.v3
# requires Python 3.12+, so it (and its tests) are skipped below that version,
# matching the compatibility table in README.md.
#

set -uo pipefail

echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install pytest coverage || exit 1
if [ -f requirements.txt ]; then
    pip install -r requirements.txt || exit 1
fi

python_supports_v3() {
    python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
}

if python_supports_v3
then
    echo "Python 3.12+: running the full suite (v1, v2, v3)..."
    coverage run -m pytest
    rc=$?
else
    echo "Python < 3.12: javaobj.v3 is unsupported, skipping it and its tests..."
    coverage run --omit='javaobj/v3/*,tests/test_v3.py' -m pytest --ignore=tests/test_v3.py
    rc=$?
fi

coverage report

exit "$rc"
