from __future__ import annotations

import os
from pathlib import Path
import threading
from typing import BinaryIO


_registry_guard = threading.Lock()
_held_in_process: set[str] = set()


class WorkerLock:
    """Non-blocking process lock that owns one download scheduler per database."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._registry_key = os.path.normcase(str(self.path.resolve()))
        self._stream: BinaryIO | None = None

    @property
    def acquired(self) -> bool:
        return self._stream is not None

    def acquire(self) -> bool:
        if self.acquired:
            return True

        with _registry_guard:
            if self._registry_key in _held_in_process:
                return False

            self.path.parent.mkdir(parents=True, exist_ok=True)
            stream = self.path.open("a+b")
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)

            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                stream.close()
                return False

            self._stream = stream
            _held_in_process.add(self._registry_key)
            return True

    def release(self) -> None:
        with _registry_guard:
            stream = self._stream
            if stream is None:
                return
            self._stream = None
            _held_in_process.discard(self._registry_key)

            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()
