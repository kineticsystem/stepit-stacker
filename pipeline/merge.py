"""The merge step: the developed frames of an angle into one image, with focus-merge."""

import subprocess


def merge(frames, merged, rotate):
    merged.parent.mkdir(parents=True, exist_ok=True)
    temporary = merged.with_name(f".{merged.name}")
    result = subprocess.run(
        ["focus-merge", "-o", str(temporary), "--rotate", str(rotate), *map(str, frames)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"focus-merge failed: {result.stderr.strip()}")
    # Moved into place once whole: a merge cut short leaves no image behind.
    temporary.replace(merged)
