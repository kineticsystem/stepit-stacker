#!/bin/bash -e

# Fails when an SVG of docs/diagrams is missing, older than its .mmd source, or
# has no source: bin/render-diagrams.sh writes the SHA-256 of the source into
# the first line of each SVG. Needs no browser, so it runs in the container.

cd "$(dirname "$(readlink -f "$0")")/.."

failed=0
for dir in docs/diagrams; do
    for source in "$dir"/*.mmd; do
        [ -f "$source" ] || continue
        svg=${source%.mmd}.svg
        hash=$(sha256sum "$source" | cut -d ' ' -f 1)
        if [ ! -f "$svg" ]; then
            echo "$svg is missing: run bin/render-diagrams.sh" >&2; failed=1
        elif ! head -n 1 "$svg" | grep -q "sha256 $hash"; then
            echo "$svg is out of date: run bin/render-diagrams.sh" >&2; failed=1
        fi
    done
    for svg in "$dir"/*.svg; do
        [ -f "$svg" ] || continue
        [ -f "${svg%.svg}.mmd" ] || { echo "$svg has no .mmd source" >&2; failed=1; }
    done
done
[ "$failed" = 0 ] && echo "The diagrams are up to date."
exit "$failed"
