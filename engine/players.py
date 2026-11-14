"""Seat adapters between the engine and bots.

SubprocessPlayer runs a bot file in its own Python process with a strict
per-decision time limit (this is what the tournament uses).
LocalPlayer runs an Agent class in-process with no time limit (handy for
house bots and quick local testing).
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import traceback

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_runner.py")


class _Stats:
    def __init__(self):
        self.decisions = 0
        self.timeouts = 0
        self.errors = 0
        self.error_samples = []
        self.max_ms = 0.0
        self.total_ms = 0.0
        self.bank_out = 0  # decisions auto-played because the time bank ran out

    def note_error(self, text, strip=None):
        if strip:
            text = text.replace(strip, "")
        self.errors += 1
        if len(self.error_samples) < 3:
            self.error_samples.append(text[-2000:])

    def as_dict(self):
        return {
            "decisions": self.decisions,
            "timeouts": self.timeouts,
            "errors": self.errors,
            "error_samples": self.error_samples,
            "max_ms": round(self.max_ms, 3),
            "avg_ms": round(self.total_ms / self.decisions, 3) if self.decisions else 0.0,
            "bank_out": self.bank_out,
        }


def _limit_resources():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
    except Exception:
        pass


class SubprocessPlayer:
    def __init__(self, bot_path, timeout_ms=10.0, setup_timeout=5.0, stderr_path=None,
                 bank_ms=None):
        """timeout_ms: limit per decision. bank_ms: total thinking time for
        this player's life (one table); once spent, every decision is
        auto-played (check, else fold) without asking the bot."""
        self.bot_path = os.path.abspath(bot_path)
        self.bank = bank_ms / 1000.0 if bank_ms is not None else None
        self._strip = os.path.dirname(self.bot_path) + os.sep
        self.timeout = timeout_ms / 1000.0
        self.setup_timeout = setup_timeout
        self.stderr_path = stderr_path
        self.stats = _Stats()
        self.proc = None
        self.lines = None
        self.flooded = False
        self.stalled = False
        self.dead = False
        self.next_id = 0

    # ----------------------------------------------------------- plumbing
    def _spawn(self):
        if self.stderr_path == "inherit":
            stderr = None  # bot prints appear in this terminal
        elif self.stderr_path:
            stderr = open(self.stderr_path, "ab")
        else:
            stderr = subprocess.DEVNULL
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "1"}
        if os.name == "nt":
            # Windows needs these to start Python at all.
            for key in ("SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP"):
                if key in os.environ:
                    env[key] = os.environ[key]
        self.proc = subprocess.Popen(
            [sys.executable, "-I", RUNNER, self.bot_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            cwd=os.path.dirname(self.bot_path), env=env,
            preexec_fn=_limit_resources if os.name == "posix" else None,
        )
        if stderr not in (None, subprocess.DEVNULL):
            stderr.close()
        self._start_io()

    def _start_io(self):
        """Background threads talk to the bot, so the dealer never blocks on it:
        waiting for a reply has a timeout on every OS, and a bot that stops
        reading its input can't freeze the table by filling the pipe."""
        self.lines = queue.Queue()
        threading.Thread(target=self._reader, args=(self.proc.stdout, self.lines),
                         daemon=True).start()
        self.outbox = queue.Queue(maxsize=self.MAX_PENDING)
        threading.Thread(target=self._writer, daemon=True).start()

    MAX_LINE = 1 << 16  # a reply longer than this is not a real reply

    @classmethod
    def _reader(cls, stream, lines):
        while True:
            line = stream.readline(cls.MAX_LINE + 1)
            if not line:
                break
            if len(line) > cls.MAX_LINE or lines.qsize() > 1000:
                lines.put(b"__flood__")  # bot is spamming the protocol: treat as dead
                break
            lines.put(line)
        lines.put(None)  # end of output: the bot process exited

    MAX_PENDING = 2000  # messages a bot may leave unread before it's cut off

    def _writer(self):
        while True:
            data = self.outbox.get()
            if data is None:
                break
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                self.dead = True
                break
        try:
            self.proc.stdin.close()
        except Exception:
            pass

    def _send(self, obj):
        if self.dead:
            return False
        try:
            self.outbox.put_nowait((json.dumps(obj) + "\n").encode())
            return True
        except queue.Full:
            self.dead = True
            self.stalled = True  # stopped reading its input
            return False

    def _readline(self, deadline):
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return None
        try:
            line = self.lines.get(timeout=remaining)
        except queue.Empty:
            return None
        if line == b"__flood__":
            self.flooded = True
            line = None
        if line is None:
            self.dead = True
        return line

    def _wait_for(self, want_id, deadline):
        """Return the reply with id `want_id`, skipping stale late replies."""
        while True:
            line = self._readline(deadline)
            if line is None:
                return None
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("type") == "load_error":
                return msg
            if msg.get("id") == want_id or (want_id is None and msg.get("type") == "loaded"):
                return msg

    # ------------------------------------------------------- engine hooks
    def start_table(self, seat, info):
        self.load_error = None
        if self.proc is None:
            self._spawn()
            msg = self._wait_for(None, time.perf_counter() + self.setup_timeout)
            if msg is None or msg.get("type") != "loaded":
                self.dead = True
                text = (msg or {}).get("error") or "Bot did not load within %.0fs" % self.setup_timeout
                self.load_error = text
                self.stats.note_error(text, self._strip)
                return
        self.next_id += 1
        if not self._send({"id": self.next_id, "type": "new_table", "info": info}):
            return
        msg = self._wait_for(self.next_id, time.perf_counter() + self.setup_timeout)
        if msg is None or msg.get("type") != "ready":
            self.dead = True
            text = (msg or {}).get("error") or "Agent() did not start within %.0fs" % self.setup_timeout
            self.load_error = text
            self.stats.note_error(text, self._strip)

    def act(self, state):
        self.stats.decisions += 1
        if self.dead:
            return None
        limit = self.timeout
        if self.bank is not None:
            if self.bank <= 0:
                self.stats.bank_out += 1
                return None
            limit = min(limit, self.bank)
        self.next_id += 1
        t0 = time.perf_counter()
        if not self._send({"id": self.next_id, "type": "act", "state": state}):
            return None
        msg = self._wait_for(self.next_id, t0 + limit)
        spent = time.perf_counter() - t0
        if self.bank is not None:
            self.bank -= min(spent, limit)
        ms = spent * 1000
        self.stats.total_ms += ms
        self.stats.max_ms = max(self.stats.max_ms, ms)
        if msg is None:
            if self.dead:
                self.stats.note_error("Bot process exited unexpectedly.")
            else:
                self.stats.timeouts += 1
            return None
        if msg.get("type") == "error":
            self.stats.note_error(msg.get("error", "unknown error"), self._strip)
            return None
        return msg

    def hand_end(self, summary):
        self._send({"type": "hand_end", "summary": summary})

    def close(self):
        if self.proc is None:
            return
        self._send({"type": "quit"})
        try:
            self.outbox.put_nowait(None)
        except queue.Full:
            pass
        try:
            self.proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


class LocalPlayer:
    def __init__(self, agent_cls):
        self.agent_cls = agent_cls
        self.agent = None
        self.stats = _Stats()

    def start_table(self, seat, info):
        self.agent = self.agent_cls()
        if hasattr(self.agent, "on_table_start"):
            self.agent.on_table_start(info)

    def act(self, state):
        from .bot_runner import normalise
        self.stats.decisions += 1
        t0 = time.perf_counter()
        try:
            out = normalise(self.agent.act(state))
        except Exception:
            self.stats.note_error(traceback.format_exc(limit=6))
            out = None
        ms = (time.perf_counter() - t0) * 1000
        self.stats.total_ms += ms
        self.stats.max_ms = max(self.stats.max_ms, ms)
        return out

    def hand_end(self, summary):
        if hasattr(self.agent, "on_hand_end"):
            try:
                self.agent.on_hand_end(summary)
            except Exception:
                pass

    def close(self):
        pass
