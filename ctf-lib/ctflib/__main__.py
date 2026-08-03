"""Command line entry points:

    python -m ctflib serve 8000        # log every incoming request (XSS/SSRF callbacks)
    python -m ctflib shell 4444        # reverse shell listener
    python -m ctflib flag 'sknb{*}' file.txt
"""

import sys

from . import App, find_flgs, reverse_shell

USAGE = __doc__


def _serve(argv):
    port = int(argv[0]) if argv else 8000
    app = App(log=True)
    app.default(lambda req, res: res.text("ok"))
    app.listen(port)


def _shell(argv):
    port = int(argv[0]) if argv else 4444
    reverse_shell(port)


def _flag(argv):
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    fmt, files = argv[0], argv[1:]
    if files:
        text = "\n".join(open(name, "r", errors="replace").read() for name in files)
    else:
        text = sys.stdin.read()
    found = find_flgs(text, fmt)
    print("\n".join(found) if found else "", end="\n" if found else "")
    return 0 if found else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE, file=sys.stderr)
        return 2
    command, rest = argv[0], argv[1:]
    if command == "serve":
        return _serve(rest)
    if command == "shell":
        return _shell(rest)
    if command == "flag":
        return _flag(rest)
    print(f"unknown command: {command}\n\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
