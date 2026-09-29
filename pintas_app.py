"""Double-click launcher for the packaged Windows app (Pintas.exe).

    Pintas.exe                     -> opens the editor on Documents\\Pintas\\panid.pintas
    Pintas.exe mysite.pintas       -> opens the editor on that file (also what
                                      drag-and-drop / "Open with" does)
    Pintas.exe a.pintas out.html   -> the normal command-line compiler

The editor is the same one `pintas.py --editor` serves, so nothing here
duplicates logic; this file only picks sensible defaults for people who
have never used a terminal.
"""
import sys
import tempfile
from pathlib import Path

import editor_toolbar  # noqa: F401  (imported lazily by pintas; named here so
import pattern_generator  # noqa: F401  PyInstaller bundles them)
import pintas
import pintas_editor
import theme_generator  # noqa: F401

DEFAULT_PORT = 8000


def default_source():
    return Path.home() / "Documents" / "Pintas" / "panid.pintas"


def launch_editor(source_path):
    source_path = Path(source_path).expanduser().resolve()
    preview_dir = Path(tempfile.gettempdir()) / "pintas-preview"
    print("=" * 56)
    print(" Pintas Editor")
    print(f" File: {source_path}")
    print(" Maluktan ti browser mo. Ikkaten daytoy a window")
    print(" (wenno pindutem ti Ctrl+C) tapno agsardeng.")
    print("=" * 56)
    pintas_editor.run_editor(source_path, preview_dir / "index.html", DEFAULT_PORT)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    args = argv[1:]
    try:
        if not args:
            launch_editor(default_source())
        elif len(args) == 1 and args[0].lower().endswith(".pintas"):
            launch_editor(args[0])
        else:
            pintas.main()  # regular CLI, reads sys.argv
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise
    except Exception as e:  # a closed window would hide the reason
        print(f"\nSayop: {e}")
        if sys.stdin and sys.stdin.isatty():
            input("Pindutem ti Enter tapno agserra...")
        raise SystemExit(1)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    main()
