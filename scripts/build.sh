#!/usr/bin/env bash

# Builds the maxed site, then each variant in variants/ into <site dir>/<variant>/.
#
# A variant is an overlay: it holds full copies of the files that differ from the
# maxed setup, at their normal repository paths. Everything not present in the
# overlay is shared, so it only ever has to be edited once.

set -euo pipefail

cd "$(dirname "$0")/.."

root=$(pwd)
site=${1:-site}
work=.variant-build
sources=(docs tags overrides main.py mkdocs.yml)

rm -rf "$site" "$work"

mkdocs build --site-dir "$site"

for overlay in variants/*/; do
    variant=$(basename "$overlay")
    build="$work/$variant"

    while read -r file; do
        target=${file#"$overlay"}

        if [[ ! -f $target ]]; then
            echo "$file overrides $target, which no longer exists" >&2
            exit 1
        fi
    done < <(find "$overlay" -type f)

    mkdir -p "$build"
    cp -a "${sources[@]}" "$build"
    cp -a "$overlay." "$build"

    (cd "$build" && mkdocs build --site-dir "$root/$site/$variant")
done

rm -rf "$work"
