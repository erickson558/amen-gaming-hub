from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "amen_hub" / "version.py"


def parse_version(line: str) -> tuple[int, int, int]:
    value = line.split("=", 1)[1].strip().strip('"')
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def bump_patch(version: tuple[int, int, int]) -> tuple[int, int, int]:
    major, minor, patch = version
    return major, minor, patch + 1


def main() -> None:
    text = VERSION_FILE.read_text(encoding="utf-8").splitlines()
    new_lines = []
    current = (0, 0, 0)

    for line in text:
        if line.startswith("APP_VERSION ="):
            current = parse_version(line)
            bumped = bump_patch(current)
            new_lines.append(f'APP_VERSION = "{bumped[0]}.{bumped[1]}.{bumped[2]}"')
        elif line.startswith("APP_VERSION_TAG ="):
            new_lines.append('APP_VERSION_TAG = f"V{APP_VERSION}"')
        else:
            new_lines.append(line)

    VERSION_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Version updated: {current[0]}.{current[1]}.{current[2]} -> {bumped[0]}.{bumped[1]}.{bumped[2]}")


if __name__ == "__main__":
    main()
