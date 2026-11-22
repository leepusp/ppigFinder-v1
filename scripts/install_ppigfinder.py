"""Local installation wizard. Run from a ppigFinder source checkout."""

import argparse
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
MANUAL_URL = "https://leepusp.github.io/ppigFinder-v1/user_manual/installation/"


def venv_python(destination):
    return destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install(destination, recommended, report):
    destination = destination.expanduser().resolve()
    python = venv_python(destination)
    report("Installing ppigFinder")
    report(f"Installation manual: {MANUAL_URL}")

    def run(*args, env=None):
        report(f"> {subprocess.list2cmdline([str(arg) for arg in args])}")
        with subprocess.Popen(
            args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace",
        ) as process:
            for line in process.stdout:
                report(line.rstrip())
            if process.wait():
                raise RuntimeError(f"Command failed with exit code {process.returncode}. See the log above.")

    if not (destination / "pyvenv.cfg").is_file():
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            raise ValueError("Choose an empty folder or an existing Python virtual environment.")
        run(sys.executable, "-m", "venv", str(destination))
    elif not python.is_file():
        raise ValueError("This virtual environment is incomplete. Choose a new installation folder.")

    run(str(python), "-c", "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'")
    extras = "gui,recommended" if recommended else "gui"
    run(str(python), "-u", "-m", "pip", "install", "--progress-bar", "off", f".[{extras}]")
    run(str(python), "-m", "pip", "check")
    run(str(python), "-I", "-c",
        "from PyQt6.QtWidgets import QApplication; from ppigfinder.app import main; app = QApplication([])",
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    if recommended:
        run(str(python), "-I", "-c", "import paramiko, pyrodigal, scipy")
    report(f"Installation complete: {destination}")
    return python


def wizard(destination, recommended):
    try:
        import tkinter as tk
        from tkinter import filedialog, ttk
    except ImportError as exc:
        raise RuntimeError("The graphical wizard requires Tk. Use --terminal to install without Tk.") from exc
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError(f"Could not initialize Tcl/Tk. Use --terminal to install.\n{exc}") from exc

    window.title("ppigFinder Setup")
    window.geometry("680x440")
    panel = ttk.Frame(window, padding=16)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="Install ppigFinder locally", font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
    ttk.Label(panel, text="Choose the folder for an isolated Python environment.").pack(anchor="w", pady=(8, 4))
    folder = tk.StringVar(value=str(destination))
    options = ttk.Frame(panel)
    options.pack(fill="x")
    entry = ttk.Entry(options, textvariable=folder)
    entry.pack(side="left", fill="x", expand=True)

    def browse():
        selected = filedialog.askdirectory(parent=window)
        if selected:
            folder.set(selected)

    picker = ttk.Button(options, text="Browse…", command=browse)
    picker.pack(side="left", padx=(8, 0))
    extras = tk.BooleanVar(value=recommended)
    checkbox = ttk.Checkbutton(panel, text="Include Pyrodigal, SciPy and SSH/SFTP support", variable=extras)
    checkbox.pack(anchor="w", pady=8)
    log = tk.Text(panel, wrap="word", state="disabled", height=12)
    log.pack(fill="both", expand=True)
    controls = ttk.Frame(panel)
    controls.pack(fill="x", pady=(10, 0))
    messages = queue.Queue()
    python = None
    busy = False

    def append(line):
        log.configure(state="normal")
        log.insert("end", line + "\n")
        log.see("end")
        log.configure(state="disabled")

    def poll():
        nonlocal busy, python
        while not messages.empty():
            kind, value = messages.get_nowait()
            if kind == "log":
                append(value)
                continue
            busy = False
            for widget in (start, entry, picker, checkbox):
                widget.configure(state="normal")
            if kind == "done":
                python = value
                launch.configure(state="normal")
            else:
                append(f"Installation failed: {value}")
        window.after(75, poll)

    def begin():
        nonlocal busy
        if not folder.get().strip():
            append("Choose an installation folder.")
            return
        target, include_extras = Path(folder.get().strip()), extras.get()
        busy = True
        for widget in (start, entry, picker, checkbox, launch):
            widget.configure(state="disabled")

        def worker():
            try:
                result = install(target, include_extras, lambda line: messages.put(("log", line)))
            except (OSError, RuntimeError, ValueError) as exc:
                messages.put(("error", exc))
            else:
                messages.put(("done", result))

        threading.Thread(target=worker).start()

    def open_app():
        try:
            subprocess.Popen(
                [str(python), "-I", "-c", "from ppigfinder.app import main; raise SystemExit(main())"],
                cwd=Path.home(),
            )
        except OSError as exc:
            append(f"Could not start ppigFinder: {exc}")

    def close():
        if busy:
            append("Wait for the current installation to finish.")
        else:
            window.destroy()

    start = ttk.Button(controls, text="Install", command=begin)
    start.pack(side="left")
    launch = ttk.Button(controls, text="Open ppigFinder", command=open_app, state="disabled")
    launch.pack(side="left", padx=8)
    ttk.Button(controls, text="Installation manual", command=lambda: webbrowser.open(MANUAL_URL)).pack(side="left")
    ttk.Button(controls, text="Close", command=close).pack(side="right")
    window.protocol("WM_DELETE_WINDOW", close)
    window.after(75, poll)
    window.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", action="store_true", help="Install without the graphical wizard")
    parser.add_argument("--destination", type=Path, default=ROOT / ".venv")
    parser.add_argument("--desktop-only", action="store_true", help="Omit Pyrodigal, SciPy and Paramiko")
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 11):
            raise RuntimeError("Python 3.11+ is required.")
        if args.terminal:
            python = install(args.destination, not args.desktop_only, lambda line: print(line, flush=True))
            print(f"Launch: {python.parent / ('ppigfinder.exe' if os.name == 'nt' else 'ppigfinder')}")
        else:
            wizard(args.destination, not args.desktop_only)
    except (OSError, RuntimeError, ValueError) as exc:
        if os.name == "nt" and sys.stderr is None:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), "ppigFinder Setup", 0x10)
            raise SystemExit(1) from exc
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
