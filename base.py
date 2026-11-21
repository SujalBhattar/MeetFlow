import tempfile
import unittest
from pathlib import Path

from database import db


class DatabaseTestCase(unittest.TestCase):
    """Runs every test against a fresh, throwaway database."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

        self._original_path = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "test.db"
        db._READY.discard(str(db.DB_PATH))

        self.addCleanup(self._restore_path)

    def _restore_path(self):
        db.DB_PATH = self._original_path
