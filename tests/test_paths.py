import importlib
import os
import tempfile
import unittest
from unittest.mock import patch

import bank
import main
import paths


class PathTest(unittest.TestCase):
    def test_import_preserves_working_directory(self):
        original = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                importlib.reload(main)
                self.assertEqual(os.getcwd(), directory)
                self.assertEqual(bank.BANK_FILE, os.path.join(paths.get_app_dir(), 'tiku.json'))
                self.assertTrue(os.path.isabs(bank.BANK_FILE))
            finally:
                os.chdir(original)

    def test_frozen_paths_use_executable_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                with patch.object(paths.sys, 'frozen', True, create=True), patch.object(paths.sys, 'executable', os.path.join(directory, 'QingmaKiller.exe')):
                    importlib.reload(bank)
                    self.assertEqual(paths.get_app_dir(), directory)
                    self.assertEqual(bank.BANK_FILE, os.path.join(directory, 'tiku.json'))
            finally:
                importlib.reload(bank)
