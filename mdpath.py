"""Check local file references in the Markdown files of a repository."""

import argparse
from dataclasses import asdict, dataclass, field
from io import TextIOWrapper
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
from urllib.parse import unquote

from mdlinks import iter_links


__version__ = "0.2.0"

IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "__pycache__", "build", "dist",
    "node_modules", "venv",
}
URL_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


@dataclass
class Report:
    files: int = 0
    links: int = 0
    broken: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def error(self, file, message):
        self.errors.append({"file": file, "message": str(message)})


def is_linklike(path):
    # Windows directory junctions can also redirect a walk outside the repo.
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def markdown_files(root, report):
    def walk_error(error):
        path = Path(error.filename or root)
        report.error(path.relative_to(root).as_posix(), error)

    for directory, dirs, files in os.walk(root, onerror=walk_error):
        base = Path(directory)
        kept = []
        for name in sorted(set(dirs) - IGNORED_DIRS):
            try:
                if not is_linklike(base / name):
                    kept.append(name)
            except OSError as error:
                report.error((base / name).relative_to(root).as_posix(), error)
        dirs[:] = kept

        for name in sorted(files):
            path = base / name
            if path.suffix.lower() not in {".md", ".markdown"}:
                continue
            try:
                if not is_linklike(path) and path.is_file():
                    yield path
            except OSError as error:
                report.error(path.relative_to(root).as_posix(), error)


def path_problem(root, base, path):
    # Encoded separators or drive letters must not redirect a filesystem lookup.
    if PureWindowsPath(path).anchor:
        return "outside-root"
    resolved = (base / path).resolve()
    if not resolved.is_relative_to(root):
        return "outside-root"
    try:
        resolved.stat()
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    return None


def check_link(root, source, line, target, report):
    if target.startswith("//") or URL_SCHEME.match(target):
        return
    raw_path = target.partition("#")[0].partition("?")[0]
    if not raw_path:
        return
    report.links += 1
    base = root if raw_path.startswith("/") else source.parent
    path = unquote(raw_path.removeprefix("/"))
    file = source.relative_to(root).as_posix()
    try:
        reason = path_problem(root, base, path)
    except (OSError, ValueError, RuntimeError) as error:
        report.error(file, f"line {line}, {target!r}: {error}")
        return
    if reason:
        report.broken.append({"file": file, "line": line, "target": target, "reason": reason})


def scan(root):
    report = Report()
    try:
        root = root.resolve(strict=True)
        if not root.is_dir():
            report.error(".", "scan root must be a directory")
            return report
    except (OSError, RuntimeError) as error:
        report.error(".", error)
        return report

    for source in markdown_files(root, report):
        try:
            content = source.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            report.error(source.relative_to(root).as_posix(), error)
            continue
        report.files += 1
        for line, target in iter_links(content):
            check_link(root, source, line, target, report)
    return report


def workflow_data(value):
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotation(file, message, line=None):
    # GitHub's command properties have two extra delimiters beyond message data.
    properties = "title=mdpath"
    if file is not None:
        properties += ",file=" + workflow_data(file).replace(":", "%3A").replace(",", "%2C")
    if line is not None:
        properties += f",line={line}"
    return f"::error {properties}::{workflow_data(message)}"


def print_annotations(root, report):
    workspace = os.environ.get("GITHUB_WORKSPACE")
    prefix = Path(".")
    if workspace:
        scan_root = Path(os.path.abspath(root))
        workspace_root = Path(os.path.abspath(workspace))
        prefix = (scan_root.relative_to(workspace_root)
                  if scan_root.is_relative_to(workspace_root) else scan_root)
    for item in report.broken:
        file = (prefix / item["file"]).as_posix()
        print(annotation(file, f"{item['reason']}: {item['target']}", item["line"]))
    for item in report.errors:
        file = None if item["file"] == "." else (prefix / item["file"]).as_posix()
        print(annotation(file, item["message"]))


def log_line(value):
    # File names and decoded destinations can contain newlines or control codes.
    result = "".join(c if c.isprintable() else ascii(c)[1:-1] for c in value)
    return result.replace("::", r":\x3a").replace("##[", r"##\[")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"mdpath {__version__}")
    parser.add_argument("root", nargs="?", type=Path, default=Path("."),
                        help="repository directory to scan (default: current directory)")
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument("--json", action="store_true", help="print a machine-readable report")
    formats.add_argument("--github", action="store_true", help="emit GitHub Actions annotations")
    args = parser.parse_args(argv)
    # Workflow commands are UTF-8; local pipes may use a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8" if args.github else stream.encoding,
                               errors="backslashreplace")
    report = scan(args.root)
    if args.json:
        payload = json.dumps(asdict(report), indent=2)
        print(payload.replace("##[", r"#\u0023["))
    else:
        if args.github:
            print_annotations(args.root, report)
        else:
            for item in report.broken:
                print(log_line("{file}:{line}: {reason}: {target}".format(**item)))
            for item in report.errors:
                print(log_line("{file}: error: {message}".format(**item)), file=sys.stderr)
        print(f"Checked {report.files} Markdown files, {report.links} local links. "
              f"Broken: {len(report.broken)}. Errors: {len(report.errors)}.")
    if report.errors:
        return 2
    return int(bool(report.broken))


if __name__ == "__main__":
    sys.exit(main())
