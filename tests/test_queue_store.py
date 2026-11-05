import importlib
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import storage
import queue_store

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db,self.base=storage.DATABASE_PATH,storage.BASE_DIR
        storage.BASE_DIR=Path(self.tmp.name)
        storage.DATABASE_PATH=storage.BASE_DIR/'test.sqlite3'
        storage.init_db()
    def tearDown(self):
        storage.DATABASE_PATH,storage.BASE_DIR=self.db,self.base
        self.tmp.cleanup()
    def test_claim_once_and_record_result(self):
        job=queue_store.enqueue('trade_1')
        claims=[]
        threads=[threading.Thread(target=lambda:claims.append(queue_store.claim())) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sum(c is not None for c in claims),1)
        self.assertEqual(next(c for c in claims if c)['id'],job)
        queue_store.append_log(job,'avvio\n')
        queue_store.finish(job,0)
        self.assertEqual(storage.jobs().iloc[0]['status'],'completed')
        queue_store.finish(job,0)  # il tentativo ripetuto non modifica l'esito
        with self.assertRaises(ValueError):queue_store.finish(job,1)
    def test_rejects_arbitrary_action(self):
        with self.assertRaises(ValueError):queue_store.enqueue('cmd.exe')

if __name__=='__main__':unittest.main()
