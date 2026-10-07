"""Hash every file in data/source and write _build/dataset_manifest.json.

    python -m datagen.manifest         (from the GovernedRAG root)

The dataset digest is the SHA-256 of the sorted "path<TAB>sha256" lines, so any
change to any file changes it.
"""

import hashlib
import json
from collections import defaultdict

from .kb import SOURCE_ROOT

OUT = SOURCE_ROOT / "_build" / "dataset_manifest.json"


def main():
    files = {}
    for p in sorted(SOURCE_ROOT.rglob("*")):
        if p.is_file() and p != OUT and p.name != ".gitkeep" and "__pycache__" not in p.parts:
            files[p.relative_to(SOURCE_ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    areas = defaultdict(list)
    for path, h in files.items():
        areas[path.split("/")[0]].append(f"{path}\t{h}")
    digest = lambda lines: hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()
    manifest = {"dataset_sha256": digest([f"{p}\t{h}" for p, h in files.items()]), "file_count": len(files),
                "areas": {a: {"files": len(lines), "sha256": digest(lines)} for a, lines in sorted(areas.items())}, "files": files}
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
