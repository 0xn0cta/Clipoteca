from __future__ import annotations

import multiprocessing
from pathlib import Path
import tempfile
import unittest

from clipoteca.worker_lock import WorkerLock


def _hold_lock(path: str, acquired, release) -> None:
    lock = WorkerLock(path)
    owned = lock.acquire()
    acquired.set()
    if owned:
        release.wait(10)
        lock.release()


def _hold_lock_until_terminated(path: str, acquired) -> None:
    lock = WorkerLock(path)
    lock.acquire()
    acquired.set()
    multiprocessing.Event().wait(30)


class WorkerLockTests(unittest.TestCase):
    def test_only_one_lock_instance_in_a_process_owns_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "worker.lock"
            first = WorkerLock(path)
            second = WorkerLock(path)

            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_lock_is_exclusive_between_processes_and_released_on_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = multiprocessing.get_context("spawn")
            path = str(Path(directory) / "worker.lock")
            acquired = context.Event()
            release = context.Event()
            process = context.Process(target=_hold_lock, args=(path, acquired, release))
            process.start()
            contender = WorkerLock(path)
            try:
                self.assertTrue(acquired.wait(5))
                self.assertFalse(contender.acquire())
                release.set()
                process.join(5)
                self.assertFalse(process.is_alive())
                self.assertEqual(process.exitcode, 0)
                self.assertTrue(contender.acquire())
            finally:
                release.set()
                if process.is_alive():
                    process.terminate()
                    process.join(5)
                contender.release()

    def test_process_termination_releases_worker_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = multiprocessing.get_context("spawn")
            path = str(Path(directory) / "worker.lock")
            acquired = context.Event()
            process = context.Process(target=_hold_lock_until_terminated, args=(path, acquired))
            process.start()
            contender = WorkerLock(path)
            try:
                self.assertTrue(acquired.wait(5))
                self.assertFalse(contender.acquire())
                process.terminate()
                process.join(5)
                self.assertFalse(process.is_alive())
                self.assertTrue(contender.acquire())
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(5)
                contender.release()


if __name__ == "__main__":
    unittest.main()
