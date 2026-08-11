#!/usr/bin/env bash
#
# Runs ./run_tests.sh inside a container for each supported Python version,
# using podman or docker. This covers the versions actions/setup-python
# cannot install on a modern runner (2.7, 3.4-3.7), extending them to the
# whole declared support matrix (see pyproject.toml classifiers).
#
# The project is pure Python, so the official ``python:<version>`` images are
# enough. javaobj.v3 requires Python 3.12+ (see run_tests.sh): earlier
# versions run the v1/v2 suite only.
#
# Usage:
#   ./run_tests_containers.sh                 # every supported version
#   ./run_tests_containers.sh 3.12 3.13       # only these versions
#   CONTAINER_ENGINE=docker ./run_tests_containers.sh
#   PYTHON_IMAGE_VARIANT=-slim ./run_tests_containers.sh 3.13   # slim images
#   COVERAGE_OUTPUT_DIR=coverage-data ./run_tests_containers.sh # keep coverage
#
# Environment:
#   CONTAINER_ENGINE       podman or docker (auto-detected, podman preferred)
#   PYTHON_IMAGE_VARIANT   suffix added to the image tag (e.g. -slim, -bookworm)
#   ENGINE_RUN_ARGS        extra arguments passed to "<engine> run"
#   COVERAGE_OUTPUT_DIR    if set, the coverage data file of each version is
#                          copied out of its container into that directory, as
#                          "coverage-py<version>.dat". Combine them with:
#                              coverage combine <dir>/*.dat && coverage report
#                          (.coveragerc maps the in-container /work paths back
#                          to the local checkout). Without it, no host file is
#                          written, as before.
#
# Exit code: 0 if every version passed, 1 if any version failed.

set -uo pipefail

# Supported Python versions, oldest first (matches pyproject.toml classifiers).
DEFAULT_VERSIONS="2.7 3.4 3.5 3.6 3.7 3.8 3.9 3.10 3.11 3.12 3.13 3.14"

# ----------------------------------------------------------------------------
# Container engine detection

ENGINE="${CONTAINER_ENGINE:-}"
if [ -z "$ENGINE" ]; then
    if command -v podman >/dev/null 2>&1; then
        ENGINE="podman"
    elif command -v docker >/dev/null 2>&1; then
        ENGINE="docker"
    else
        echo "error: neither podman nor docker was found in PATH" >&2
        exit 1
    fi
fi

if ! command -v "$ENGINE" >/dev/null 2>&1; then
    echo "error: container engine '$ENGINE' not found in PATH" >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# Arguments

if [ "$#" -gt 0 ]; then
    case "$1" in
        -h | --help)
            sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
    esac
    VERSIONS="$*"
else
    VERSIONS="$DEFAULT_VERSIONS"
fi

# Directory holding this script (and run_tests.sh)
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$REPO_DIR/run_tests.sh" ]; then
    echo "error: run_tests.sh not found next to this script" >&2
    exit 1
fi

# Extra "run" arguments (word-split on purpose)
# shellcheck disable=SC2206
EXTRA_RUN_ARGS=(${ENGINE_RUN_ARGS:-})

# Directory where the coverage data files are exported (empty: don't export)
COVERAGE_DIR="${COVERAGE_OUTPUT_DIR:-}"
if [ -n "$COVERAGE_DIR" ]; then
    if ! mkdir -p "$COVERAGE_DIR"; then
        echo "error: cannot create coverage output directory $COVERAGE_DIR" >&2
        exit 1
    fi

    # Absolute path, so it stays valid whatever the current directory
    COVERAGE_DIR="$(cd "$COVERAGE_DIR" && pwd)"
fi

# ----------------------------------------------------------------------------
# Helpers

# Returns the image reference for a Python version. Images are fully
# qualified so that podman does not prompt for a registry.
image_for() {
    local version="$1"
    local variant="${PYTHON_IMAGE_VARIANT:-}"
    echo "docker.io/library/python:${version}${variant}"
}

# Files and folders that must not be copied into the container: host virtual
# environments, caches and build artifacts would shadow a clean checkout.
TAR_EXCLUDES=(
    --exclude=./.git
    --exclude=./.venv
    --exclude='./venv*'
    --exclude=./build
    --exclude=./dist
    --exclude='./*.egg-info'
    --exclude=./.coverage
    --exclude='./.coverage.*'
    --exclude=./htmlcov
    --exclude='./__pycache__'
    --exclude='*.pyc'
    --exclude=./.pytest_cache
    --exclude=./.ruff_cache
    --exclude=./.mypy_cache
    --exclude=./.tox
    --exclude=./tests/java/target
)

# ----------------------------------------------------------------------------
# Run

echo "Engine:   $ENGINE"
echo "Versions: $VERSIONS"
echo

declare -a SUMMARY
overall_rc=0

for version in $VERSIONS; do
    image="$(image_for "$version")"

    echo "============================================================"
    echo ">>> Python $version  ($image)"
    echo "============================================================"

    # When the coverage data is to be kept, the container must survive the run
    # so that it can be copied out: it is named and removed explicitly instead
    # of relying on --rm.
    container="javaobj-tests-${version}-$$"
    if [ -n "$COVERAGE_DIR" ]; then
        RUN_ARGS=(--name "$container" -i)
        "$ENGINE" rm -f "$container" >/dev/null 2>&1
    else
        RUN_ARGS=(--rm -i)
    fi

    # The working tree is streamed into the container over stdin (a tar pipe)
    # rather than bind-mounted: no host file is modified (unless the coverage
    # data is explicitly exported below), and there is no SELinux relabeling to
    # worry about.
    # The workdir is created inside the shell (podman does not create --workdir
    # by itself); run_tests.sh is invoked through bash so it does not depend on
    # the executable bit surviving the tar round-trip.
    tar "${TAR_EXCLUDES[@]}" -C "$REPO_DIR" -cf - . \
        | "$ENGINE" run "${RUN_ARGS[@]}" \
            "${EXTRA_RUN_ARGS[@]}" \
            "$image" \
            bash -c 'mkdir -p /work && cd /work && tar -xf - && exec bash run_tests.sh'
    rc=${PIPESTATUS[1]}

    if [ -n "$COVERAGE_DIR" ]; then
        if "$ENGINE" cp "$container:/work/.coverage" \
                "$COVERAGE_DIR/coverage-py${version}.dat" 2>/dev/null; then
            echo ">>> Python $version: coverage data exported"
        else
            echo ">>> Python $version: no coverage data to export" >&2
        fi

        "$ENGINE" rm -f "$container" >/dev/null 2>&1
    fi

    if [ "$rc" -eq 0 ]; then
        echo ">>> Python $version: PASS"
        SUMMARY+=("PASS  Python $version")
    else
        echo ">>> Python $version: FAIL (exit $rc)"
        SUMMARY+=("FAIL  Python $version (exit $rc)")
        overall_rc=1
    fi
    echo
done

# ----------------------------------------------------------------------------
# Summary

echo "============================================================"
echo "Summary"
echo "============================================================"
for line in "${SUMMARY[@]}"; do
    echo "  $line"
done

exit "$overall_rc"
