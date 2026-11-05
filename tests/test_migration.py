import sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
import storage
from migration_export import export
from migration_restore import restore
class MigrationTests(unittest.TestCase):
 def test_preserves_original_and_restores_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);old_db,old_base=storage.DATABASE_PATH,storage.BASE_DIR
   storage.BASE_DIR=root/'old';storage.DATABASE_PATH=storage.BASE_DIR/'wefix_prices.sqlite3'
   try:
    storage.init_db();storage.import_rows([['Modello','Colore','128 GB'],['iPhone','Nero',100]],kind='sale',source_id='test',filename='test',sheet_name='Apple',scanned_at='2026-01-01',is_primary=True)
    job=storage.new_job('sale',storage.BASE_DIR/'jobs'/'sale.log')
    (storage.BASE_DIR/'jobs').mkdir();(storage.BASE_DIR/'jobs'/'sale.log').write_text('test log',encoding='utf-8')
    storage.update_job(job,status='completed',exit_code=0)
    incoming=root/'incoming';counts=export(storage.DATABASE_PATH,incoming)
    self.assertEqual(counts['prices'],1)
    with closing(sqlite3.connect(incoming/'wefix_prices.sqlite3')) as db:
     self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0].lower(),'delete')
    target=root/'volume'/'wefix_prices.sqlite3'
    self.assertTrue(restore(incoming/'wefix_prices.sqlite3',target))
    self.assertFalse(restore(incoming/'wefix_prices.sqlite3',target))
    with closing(sqlite3.connect(target)) as db:
     self.assertEqual(db.execute('select count(*) from prices').fetchone()[0],1)
     self.assertEqual(db.execute('select log_file from jobs').fetchone()[0],'/app/data/jobs/1.log')
    self.assertEqual((root/'volume/jobs/1.log').read_text(), 'test log')
    with closing(sqlite3.connect(storage.DATABASE_PATH)) as db:
     self.assertIn('sale.log',db.execute('select log_file from jobs').fetchone()[0])
   finally:storage.DATABASE_PATH,storage.BASE_DIR=old_db,old_base
 def test_refuses_active_jobs(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);old_db,old_base=storage.DATABASE_PATH,storage.BASE_DIR
   storage.BASE_DIR=root;storage.DATABASE_PATH=root/'old.sqlite3'
   try:
    storage.init_db();storage.new_job('sale',root/'jobs/a.log')
    with self.assertRaises(ValueError): export(storage.DATABASE_PATH,root/'incoming')
   finally:storage.DATABASE_PATH,storage.BASE_DIR=old_db,old_base
if __name__=='__main__':unittest.main()
