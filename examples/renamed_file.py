"""Run a broken-link and repair example in a disposable directory."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


CLI = Path(__file__).resolve().parents[1] / "mdpath.py"


def main():
    with TemporaryDirectory() as folder:
        root = Path(folder)
        source = root / "README.md"
        original = root / "data" / "run 01.csv"
        original.parent.mkdir()
        original.write_text("sample,count\nA,42\n", encoding="utf-8")
        note = "# Experiment\n\n[Results](<data/run 01.csv>)\n"
        source.write_text(note, encoding="utf-8")
        original.rename(original.with_name("run 02.csv"))

        print("After renaming the CSV:", flush=True)
        command = [sys.executable, "-B", str(CLI), str(root)]
        broken = subprocess.run(command)
        if broken.returncode != 1:
            raise SystemExit("Expected exit code 1 for the renamed file")

        print("\nAfter updating the Markdown link:", flush=True)
        source.write_text(note.replace("run 01.csv", "run 02.csv"), encoding="utf-8")
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
