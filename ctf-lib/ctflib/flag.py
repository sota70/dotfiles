"""Flag extraction based on a wildcard format string.

    find_flg("Here is your flag: sknb{flag}", "sknb{*}")   # -> 'sknb{flag}'

Wildcards
    ``*``   any run of characters (non-greedy by default)
    ``?``   exactly one character
    ``\\*``  a literal ``*`` (same for ``\\?``)
"""

from __future__ import annotations

import os
import re

__all__ = [
    "find_flg",
    "find_flgs",
    "find_flag",
    "find_flags",
    "set_flag_format",
    "get_flag_format",
    "format_to_regex",
]

#: Fallback format used when ``fmt`` is omitted. Also read from $CTF_FLAG_FORMAT.
_DEFAULT_FORMAT = os.environ.get("CTF_FLAG_FORMAT") or None


def set_flag_format(fmt):
    """Set the format used when :func:`find_flg` is called without one."""
    global _DEFAULT_FORMAT
    _DEFAULT_FORMAT = fmt
    return fmt


def get_flag_format():
    return _DEFAULT_FORMAT


def format_to_regex(fmt, greedy=False, dotall=False):
    """Compile a wildcard flag format into a regex."""
    star = ".*" if greedy else ".*?"
    out = []
    i = 0
    while i < len(fmt):
        char = fmt[i]
        if char == "\\" and i + 1 < len(fmt):
            out.append(re.escape(fmt[i + 1]))
            i += 2
            continue
        if char == "*":
            out.append(star)
        elif char == "?":
            out.append(".")
        else:
            out.append(re.escape(char))
        i += 1
    return re.compile("".join(out), re.DOTALL if dotall else 0)


def _as_text(source):
    """Accept str, bytes, a Response, or any iterable of those."""
    if source is None:
        return ""
    if isinstance(source, str):
        return source
    if isinstance(source, (bytes, bytearray)):
        return bytes(source).decode("utf-8", "replace")
    text = getattr(source, "text", None)  # Response-like
    if isinstance(text, str):
        return text
    if isinstance(source, (list, tuple, set, frozenset)):
        return "\n".join(_as_text(item) for item in source)
    return str(source)


def find_flg(s, fmt=None, *, greedy=False, dotall=False, default=None):
    """Return the first substring of *s* matching the flag format *fmt*.

    *s* may be a string, bytes, a :class:`~ctflib.client.Response`, or a list of
    those. Returns *default* (``None``) when nothing matches.
    """
    fmt = fmt or _DEFAULT_FORMAT
    if not fmt:
        raise ValueError("no flag format given -- pass fmt= or call set_flag_format()")
    match = format_to_regex(fmt, greedy, dotall).search(_as_text(s))
    return match.group(0) if match else default


def find_flgs(s, fmt=None, *, greedy=False, dotall=False, unique=True):
    """Return every match of *fmt* in *s* (order preserved)."""
    fmt = fmt or _DEFAULT_FORMAT
    if not fmt:
        raise ValueError("no flag format given -- pass fmt= or call set_flag_format()")
    found = [m.group(0) for m in format_to_regex(fmt, greedy, dotall).finditer(_as_text(s))]
    if not unique:
        return found
    return list(dict.fromkeys(found))


# Aliases -- "flg" is the spec's name, "flag" is the one people type by mistake.
find_flag = find_flg
find_flags = find_flgs
