import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

class LiveLogTests(unittest.TestCase):
    def test_start_shows_log_and_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / 'prices.sqlite3')
            with patch.dict(os.environ, {'WEFIX_DB_PATH': db_path}):
                import storage
                old_path = storage.DATABASE_PATH
                old_base = storage.BASE_DIR
                storage.DATABASE_PATH = Path(db_path)
                storage.BASE_DIR = Path(tmp)
                try:
                    at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
                    at.sidebar.radio[0].set_value('Esecuzioni').run()
                    with patch('subprocess.Popen'):
                        at.button(key='sale').click().run()
                    self.assertFalse(at.exception)
                    self.assertTrue(any('Esecuzione #1' in item.value for item in at.markdown))
                    self.assertTrue(any('In attesa' in item.value for item in at.markdown))
                    with storage.connection() as db:
                        path = Path(db.execute('SELECT log_file FROM jobs WHERE id=1').fetchone()[0])
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text('Prova log in tempo reale', encoding='utf-8')
                    storage.update_job(1, status='failed', exit_code=1, error='Errore simulato')
                    at.run()
                    self.assertFalse(at.exception)
                    self.assertTrue(any('Fallita' in item.value for item in at.markdown))
                    self.assertTrue(any('Prova log in tempo reale' in item.value for item in at.code))
                finally:
                    storage.DATABASE_PATH = old_path
                    storage.BASE_DIR = old_base

if __name__ == '__main__':
    unittest.main()
