"""Reject malformed manifests and ensure each direct requirement has a compatible pin."""

import re
import tomllib
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def validate(root):
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8-sig"))
    assert project["tool"]["setuptools"]["dynamic"]["dependencies"]["file"] == ["requirements.txt"]
    pins = {}
    for filename in ("requirements.lock.txt", "requirements.txt"):
        names = set()
        text = (root / filename).read_text(encoding="utf-8-sig")
        assert not re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.M), (
            "Merge markers in dependencies"
        )
        for line in text.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            requirement = Requirement(line)
            name = canonicalize_name(requirement.name)
            assert name not in names, f"Duplicate requirement: {name}"
            assert name not in {"main", "master", "backend-branch"}, "Branch label in dependencies"
            names.add(name)
            if filename.endswith("lock.txt"):
                specs = list(requirement.specifier)
                assert len(specs) == 1 and specs[0].operator == "==", "Lock must use exact pins"
                pins[name] = specs[0].version
            else:
                assert name in pins and requirement.specifier.contains(pins[name]), (
                    f"Lock mismatch: {name}"
                )
    return len(pins)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(f"Validated {validate(root)} pinned dependencies")
