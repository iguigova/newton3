"""The page runs this repo's own code in the browser, on the files that
demo/files.txt names. It names every module, test and data file the page's
commands read, and nothing else."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "demo" / "files.txt"
READ = (
    "pyproject.toml",
    "src/newton/*.py",
    "analysis/*.py",
    "tests/*.py",
    "docs/artifacts/*Metabase.csv",
    "demo/files.txt",
)


def test_the_page_loads_every_file_its_commands_read():
    named = set(MANIFEST.read_text().splitlines()) - {""}
    found = {
        p.relative_to(ROOT).as_posix() for g in READ for p in ROOT.glob(g)
    }
    assert named == found
