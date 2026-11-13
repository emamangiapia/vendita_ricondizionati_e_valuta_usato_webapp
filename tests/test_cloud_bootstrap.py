import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import storage
from cloud_bootstrap import initialize_cloud

class CloudBootstrapTests(unittest.TestCase):
 def test_empty_init_requires_explicit_flag(self):
  with tempfile.TemporaryDirectory() as d,patch.object(storage,'DATABASE_PATH',Path(d)/'wefix_prices.sqlite3'),patch.dict(os.environ,{},clear=True):
   with self.assertRaises(RuntimeError):initialize_cloud()
   with patch.dict(os.environ,{'WEFIX_INITIALIZE_EMPTY':'true'}):initialize_cloud()
   self.assertTrue(storage.DATABASE_PATH.is_file())
 def test_import_once_and_refuse_to_replace_live_data(self):
  with tempfile.TemporaryDirectory() as d,patch.object(storage,'DATABASE_PATH',Path(d)/'wefix_prices.sqlite3'):
   target=storage.DATABASE_PATH
   with patch.dict(os.environ,{'WEFIX_INITIALIZE_EMPTY':'true'}):initialize_cloud()
   incoming=target.parent/'incoming.sqlite3'
   with sqlite3.connect(incoming) as db:
    db.execute('CREATE TABLE preservation_marker(value TEXT)');db.execute("INSERT INTO preservation_marker VALUES ('original')")
   with patch.dict(os.environ,{'WEFIX_IMPORT_STAGED_DB':'true'}):initialize_cloud()
   incoming.unlink()
   with patch.dict(os.environ,{'WEFIX_IMPORT_STAGED_DB':'true'}):initialize_cloud()
   with sqlite3.connect(target) as db:self.assertEqual(db.execute('SELECT value FROM preservation_marker').fetchone()[0],'original')
   (target.parent/'.drive-import-completed').unlink()
   with sqlite3.connect(target) as db:db.execute("INSERT INTO jobs(action,status) VALUES('sale','completed')")
   with sqlite3.connect(incoming) as db:db.execute('CREATE TABLE marker(value TEXT)')
   with patch.dict(os.environ,{'WEFIX_IMPORT_STAGED_DB':'true'}):
    with self.assertRaises(RuntimeError):initialize_cloud()
   with sqlite3.connect(target) as db:self.assertEqual(db.execute('SELECT value FROM preservation_marker').fetchone()[0],'original')
