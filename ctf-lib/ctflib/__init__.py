"""ctflib -- a small toolbox for CTF web challenges. No external dependencies.

    from ctflib import post, find_flg, route, listen, reverse_shell

    r = post("http://target/login", data={"user": "admin", "pw": "' OR 1--"})
    print(find_flg(r.text, "sknb{*}"))

Contents
    HTTP client   request / get / post / ... , Session, data= json= form= proxy=
    Flags         find_flg, find_flgs (wildcard formats such as ``sknb{*}``)
    Web server    App, @route("/path") annotation, listen(port)  -- express style
    Reverse shell reverse_shell(port)
"""

from .client import (
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    Headers,
    Response,
    Session,
    default_session,
    delete,
    encode_multipart,
    get,
    head,
    options,
    patch,
    post,
    put,
    request,
    session,
)
from .flag import (
    find_flag,
    find_flags,
    find_flg,
    find_flgs,
    format_to_regex,
    get_flag_format,
    set_flag_format,
)
from .server import App
from .server import Request as ServerRequest
from .server import Response as ServerResponse
from .server import app, hits, listen, route, wait_hit
from .shell import UPGRADE_PAYLOADS, reverse_shell, revshell

__version__ = "1.0.0"

__all__ = [
    # http client
    "request", "get", "post", "put", "patch", "delete", "head", "options",
    "Session", "session", "default_session", "Response", "Headers",
    "encode_multipart", "DEFAULT_TIMEOUT", "DEFAULT_USER_AGENT",
    # flags
    "find_flg", "find_flgs", "find_flag", "find_flags",
    "set_flag_format", "get_flag_format", "format_to_regex",
    # web server
    "App", "route", "listen", "app", "hits", "wait_hit",
    "ServerRequest", "ServerResponse",
    # reverse shell
    "reverse_shell", "revshell", "UPGRADE_PAYLOADS",
    "__version__",
]
