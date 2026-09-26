"""The terminal chat in a real pseudo-terminal. Textual's own test driver draws to no terminal, so
it cannot see what the app leaves behind: whether the screen, the cursor and mouse reporting are
given back, and what status the process exits with. Each test starts `python -m sympose.cli` in a
scratch directory (own profiles, settings and vault) whose model server accepts a connection and
never answers, so a turn stays pending for as long as the test wants."""

import json
import os
import select
import socket
import subprocess
import sys
import threading
import time

import pytest

pty = pytest.importorskip("pty")  # not on Windows
import fcntl  # noqa: E402
import struct  # noqa: E402
import termios  # noqa: E402

ALT_SCREEN_ON = b"\x1b[?1049h"
READY = b"Type a message"  # the greeting line, drawn last on start
RESTORED = {
    "leaves the alternate screen": b"\x1b[?1049l",
    "shows the cursor": b"\x1b[?25h",
    "turns mouse reporting off": b"\x1b[?1000l",
    "turns bracketed paste off": b"\x1b[?2004l",
}
QUIT_EXIT_SECONDS = 10  # a quit that waited for the hung model call would take far longer


@pytest.fixture
def hung_model_server():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    held = []

    def accept():
        while True:
            try:
                held.append(server.accept()[0])  # accepted, never answered
            except OSError:
                return

    threading.Thread(target=accept, daemon=True).start()
    yield server.getsockname()[1]
    server.close()
    for connection in held:
        connection.close()


class Terminal:
    def __init__(self, tmp_path, port, with_persona=True):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "Note.md").write_text("# Note\n\nhello\n")
        profiles = tmp_path / "profiles"
        profiles.mkdir()
        if with_persona:
            (profiles / "samantha").mkdir()
            (profiles / "samantha" / "persona.yaml").write_text(
                "name: Samantha\nhandle: samantha\nvault_folders: '*'\n"
            )
        (tmp_path / "settings.json").write_text(
            json.dumps({"grounding_search": "keywords", "session_recaps": False})
        )
        env = dict(
            os.environ,
            VAULT_PATHS=str(vault),
            SYMPOSE_PROFILES_DIR=str(profiles),
            SYMPOSE_SETTINGS_PATH=str(tmp_path / "settings.json"),
            OLLAMA_API_BASE=f"http://127.0.0.1:{port}",
            TERM="xterm-256color",
        )
        self.master, slave = pty.openpty()
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        self.process = subprocess.Popen(
            [sys.executable, "-m", "sympose.cli"],
            stdin=slave, stdout=slave, stderr=slave, cwd=tmp_path, env=env, start_new_session=True,
        )
        os.close(slave)
        self.output = b""

    def read(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            ready, _, _ = select.select([self.master], [], [], 0.05)
            if ready:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError:
                    return
                if not chunk:
                    return
                self.output += chunk

    def settle(self, timeout: float = 30) -> None:
        """Read until the app has drawn its greeting, so it is ready for a key. (It never goes quiet:
        it keeps redrawing on timers.)"""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.read(0.2)
            if ALT_SCREEN_ON in self.output and READY in self.output:
                self.read(0.5)
                return
        raise AssertionError("the app never finished drawing")

    def type(self, keys: bytes) -> None:
        os.write(self.master, keys)

    def wait_for_exit(self, seconds: float) -> tuple[int | None, float]:
        """`(exit status, seconds it took)`; the status is `None` if it was still running (and is killed)."""
        started = time.monotonic()
        while time.monotonic() - started < seconds:
            self.read(0.1)
            if self.process.poll() is not None:
                break
        took = time.monotonic() - started
        status = self.process.poll()
        if status is None:
            self.process.kill()
            self.process.wait()
        self.read(0.3)
        return status, took

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        os.close(self.master)

    def missing_restores(self) -> list[str]:
        return [what for what, sequence in RESTORED.items() if sequence not in self.output]


@pytest.fixture
def terminal(tmp_path, hung_model_server):
    made = []

    def start(**kwargs):
        made.append(Terminal(tmp_path, hung_model_server, **kwargs))
        return made[-1]

    yield start
    for each in made:
        each.close()


def test_ctrl_q_with_a_reply_still_pending_gives_the_terminal_back(terminal):
    """#65: quitting while a model call was running skipped the terminal teardown."""
    chat = terminal()
    chat.settle()
    chat.type(b"hello there\r")  # the model never answers, so this stays pending
    chat.read(1.5)
    chat.type(b"\x11")  # ctrl+q

    status, took = chat.wait_for_exit(QUIT_EXIT_SECONDS)

    assert status == 0 and took < QUIT_EXIT_SECONDS
    assert chat.missing_restores() == []


def test_slash_quit_with_two_messages_pending_gives_the_terminal_back(terminal):
    chat = terminal()
    chat.settle()
    chat.type(b"hello there\r")
    chat.read(1.0)
    chat.type(b"and a second one\r")  # queued behind the first
    chat.read(1.0)
    chat.type(b"/quit\r")

    status, took = chat.wait_for_exit(QUIT_EXIT_SECONDS)

    assert status == 0 and took < QUIT_EXIT_SECONDS
    assert chat.missing_restores() == []


def test_a_failed_start_exits_with_an_error_status_and_gives_the_terminal_back(terminal):
    """#66: the process exited 0 whatever happened (here: no persona to talk to)."""
    chat = terminal(with_persona=False)

    status, _ = chat.wait_for_exit(30)

    assert status not in (None, 0)
    assert chat.missing_restores() == []
