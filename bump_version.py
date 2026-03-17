from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "amen_hub" / "version.py"
VERSION_PATTERN = re.compile(r'^APP_VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$')


def parse_version(line: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.match(line.strip())
    if not match:
        raise ValueError(f"Formato de APP_VERSION invalido: {line!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_patch(version: tuple[int, int, int]) -> tuple[int, int, int]:
    major, minor, patch = version
    return major, minor, patch + 1


def main() -> None:
    text = VERSION_FILE.read_text(encoding="utf-8").splitlines()
    new_lines = []
    current: tuple[int, int, int] | None = None
    bumped: tuple[int, int, int] | None = None

    for line in text:
        if line.strip().startswith("APP_VERSION ="):
            current = parse_version(line)
            bumped = bump_patch(current)
            new_lines.append(f'APP_VERSION = "{bumped[0]}.{bumped[1]}.{bumped[2]}"')
        elif line.strip().startswith("APP_VERSION_TAG ="):
            new_lines.append('APP_VERSION_TAG = f"V{APP_VERSION}"')
        else:
            new_lines.append(line)

    if current is None or bumped is None:
        raise RuntimeError("No se encontro APP_VERSION en amen_hub/version.py")

    VERSION_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Version updated: {current[0]}.{current[1]}.{current[2]} -> {bumped[0]}.{bumped[1]}.{bumped[2]}")


if __name__ == "__main__":
    main()
