"""Repo-root conftest: loads pytest-homeassistant-custom-component explicitly.

The plugin autoloads via a pytest11 entry point on every pytest run once
installed, but importing it on Windows fails immediately (imports `fcntl`,
Unix-only) before any test collects. `-p no:homeassistant` in pyproject.toml
blocks that autoload; this file loads the plugin back explicitly, with
Windows compatibility shims applied first. pytest only honors
`pytest_plugins` in the rootdir conftest, so this cannot live in
tests/conftest.py.
"""

import sys
import types

if sys.platform == "win32":
    if "fcntl" not in sys.modules:
        fake_fcntl = types.ModuleType("fcntl")
        fake_fcntl.LOCK_SH = 1
        fake_fcntl.LOCK_EX = 2
        fake_fcntl.LOCK_NB = 4
        fake_fcntl.LOCK_UN = 8
        fake_fcntl.flock = lambda *args, **kwargs: None
        fake_fcntl.lockf = lambda *args, **kwargs: None
        fake_fcntl.fcntl = lambda *args, **kwargs: 0
        fake_fcntl.ioctl = lambda *args, **kwargs: 0
        sys.modules["fcntl"] = fake_fcntl

    if "resource" not in sys.modules:
        fake_resource = types.ModuleType("resource")
        fake_resource.RLIMIT_NOFILE = 7
        fake_resource.RLIM_INFINITY = -1
        fake_resource.getrlimit = lambda *args, **kwargs: (8192, 8192)
        fake_resource.setrlimit = lambda *args, **kwargs: None
        sys.modules["resource"] = fake_resource

    import socket as _socket_mod

    _orig_socketpair = _socket_mod.socketpair

    def _shimmed_socketpair(*args, **kwargs):
        blocked = getattr(_socket_mod.socket, "__module__", "") == "pytest_socket"
        if not blocked:
            return _orig_socketpair(*args, **kwargs)
        import pytest_socket

        pytest_socket.enable_socket()
        try:
            return _orig_socketpair(*args, **kwargs)
        finally:
            pytest_socket.socket_allow_hosts(["127.0.0.1"])
            pytest_socket.disable_socket(allow_unix_socket=True)

    _socket_mod.socketpair = _shimmed_socketpair

pytest_plugins = "pytest_homeassistant_custom_component.plugins"
