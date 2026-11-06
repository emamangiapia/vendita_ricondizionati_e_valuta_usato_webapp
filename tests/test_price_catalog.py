import importlib, os, tempfile, unittest
from pathlib import Path

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.previous=os.environ.get('WEFIX_DB_PATH'); os.environ['WEFIX_DB_PATH']=str(Path(self.tmp.name)/'test.sqlite3')
        import storage, price_catalog
        self.storage=importlib.reload(storage); self.catalog=price_catalog; self.storage.init_db()
    def tearDown(self):
        if self.previous is None: os.environ.pop('WEFIX_DB_PATH',None)
        else: os.environ['WEFIX_DB_PATH']=self.previous
        self.tmp.cleanup()
    def ingest(self, value, stamp, src):
        self.storage.import_rows([['Modello','Colori','128 GB'],['iPhone 14','Blu',value]],kind='tradein',source_id=src,filename='x',sheet_name='swappie.com',scanned_at=stamp,is_primary=False)
    def test_baseline_manual_reject_and_auto(self):
        with self.storage.connection() as db: self.catalog.rules(db,'tradein','manual',None,None)
        self.ingest(100,'2026-01-01','a')
        with self.storage.connection() as db:
            self.catalog.reconcile(db,'tradein'); self.assertEqual(db.execute('select approved from catalog_prices').fetchone()[0],100)
        self.ingest(90,'2026-02-01','b')
        with self.storage.connection() as db:
            row=db.execute('select approved,proposed from catalog_prices').fetchone(); self.assertEqual(tuple(row),(100,90))
            event=db.execute("select id from catalog_events where status='pending'").fetchone()[0]; self.catalog.decide(db,[event],'reject','walter')
        self.ingest(90,'2026-03-01','c')
        with self.storage.connection() as db:
            self.assertEqual(db.execute("select count(*) from catalog_events where status='pending'").fetchone()[0],0)
            with self.assertRaises(ValueError): self.catalog.rules(db,'tradein','auto',None,None)
            self.catalog.rules(db,'tradein','auto',5,15)
        self.ingest(92,'2026-04-01','d')
        with self.storage.connection() as db:
            self.assertEqual(db.execute('select approved from catalog_prices').fetchone()[0],92)
        self.ingest(40,'2026-05-01','e')
        with self.storage.connection() as db:
            self.assertEqual(tuple(db.execute('select approved,proposed from catalog_prices').fetchone()),(92,40))
            event=db.execute("select id from catalog_events where status='pending'").fetchone()[0]; self.catalog.decide(db,[event],'approve','emanuele')
            self.assertEqual(db.execute('select approved from catalog_prices').fetchone()[0],40)
    def test_automatic_defaults_and_existing_manual_override(self):
        with self.storage.connection() as db:
            self.assertEqual(tuple(db.execute("select mode,up_limit,down_limit from catalog_state where kind='tradein'").fetchone()), ('auto',10,10))
            self.catalog.rules(db,'tradein','manual',None,None)
        self.storage.init_db()
        with self.storage.connection() as db:
            self.assertEqual(db.execute("select mode from catalog_state where kind='tradein'").fetchone()[0], 'manual')

    def test_automatic_thresholds_and_new_product(self):
        self.ingest(100,'2026-01-01','a')
        with self.storage.connection() as db: self.catalog.reconcile(db,'tradein')
        self.ingest(110,'2026-02-01','b')
        with self.storage.connection() as db:
            self.assertEqual(tuple(db.execute('select approved,proposed from catalog_prices').fetchone()), (110,None))
        self.ingest(125,'2026-03-01','c')
        with self.storage.connection() as db:
            self.assertEqual(tuple(db.execute('select approved,proposed from catalog_prices').fetchone()), (110,125))
            self.assertEqual(len(self.catalog.notifications(db,'walter')), 1)

    def test_upgrade_approves_only_in_range_pending_once(self):
        self.ingest(100,'2026-01-01','a')
        with self.storage.connection() as db: self.catalog.reconcile(db,'tradein')
        with self.storage.connection() as db:
            self.catalog.rules(db,'tradein','manual',None,None)
        self.ingest(105,'2026-02-01','b')
        with self.storage.connection() as db:
            db.execute('DELETE FROM catalog_migrations')
        self.storage.init_db()
        with self.storage.connection() as db:
            self.assertEqual(tuple(db.execute('select approved,proposed from catalog_prices').fetchone()), (105,None))
            self.assertEqual(db.execute("select count(*) from catalog_events where status='pending'").fetchone()[0], 0)
            self.assertEqual(db.execute("select count(*) from catalog_events where status='auto'").fetchone()[0], 1)
            self.catalog.rules(db,'tradein','manual',None,None)
        self.storage.init_db()
        with self.storage.connection() as db:
            self.assertEqual(db.execute("select mode from catalog_state where kind='tradein'").fetchone()[0], 'manual')

    def test_upgrade_keeps_anomalies_and_new_variants_pending(self):
        self.ingest(100,'2026-01-01','a')
        with self.storage.connection() as db:
            self.catalog.reconcile(db,'tradein')
            self.catalog.rules(db,'tradein','manual',None,None)
        self.ingest(130,'2026-02-01','b')
        self.storage.import_rows([['Modello','Colori','128 GB'],['iPhone 14','Rosso',50]],kind='tradein',source_id='c',filename='x',sheet_name='swappie.com',scanned_at='2026-03-01')
        with self.storage.connection() as db: db.execute('DELETE FROM catalog_migrations')
        self.storage.init_db()
        with self.storage.connection() as db:
            self.assertEqual(tuple(db.execute("select approved,proposed from catalog_prices where color='Blu'").fetchone()), (100,130))
            self.assertEqual(tuple(db.execute("select approved,proposed from catalog_prices where color='Rosso'").fetchone()), (None,50))
            self.assertEqual(len(self.catalog.notifications(db,'walter')), 2)

    def test_late_historical_import_does_not_roll_back(self):
        self.ingest(100,'2026-06-01','a')
        with self.storage.connection() as db: self.catalog.reconcile(db,'tradein')
        self.ingest(30,'2025-01-01','old')
        with self.storage.connection() as db: self.assertEqual(db.execute('select approved from catalog_prices').fetchone()[0],100)
    def test_new_variants_notifications_and_multi_decisions(self):
        self.ingest(100,'2026-01-01','a')
        with self.storage.connection() as db: self.catalog.reconcile(db,'tradein')
        self.storage.import_rows([['Modello','Colori','128 GB'],['iPhone 14','Rosso',50]],kind='tradein',source_id='b',filename='x',sheet_name='swappie.com',scanned_at='2026-02-01')
        with self.storage.connection() as db:
            row=db.execute("select * from catalog_prices where color='Rosso'").fetchone();self.assertIsNone(row['approved']);self.assertEqual(row['proposed'],50)
            event=self.catalog.notifications(db,'walter')[0];self.assertFalse(event['is_read'])
            self.catalog.mark_read(db,'walter',[event['id']]);self.assertTrue(self.catalog.notifications(db,'walter')[0]['is_read']);self.assertFalse(self.catalog.notifications(db,'emanuele')[0]['is_read'])
            with self.assertRaises(ValueError): self.catalog.decide(db,[event['id'],999999],'approve','walter')
            self.assertEqual(db.execute('select approved from catalog_prices where id=?',(row['id'],)).fetchone()[0],None)
            self.catalog.decide(db,[event['id']],'approve','walter')
            self.assertEqual(db.execute('select approved from catalog_prices where id=?',(row['id'],)).fetchone()[0],50)
            self.catalog.manual_price(db,{'kind':'sale','source':'principale','model':'iPhone 15','color':'Blu','storage_gb':128,'price':333},'walter')
            self.assertEqual(db.execute("select approved from catalog_prices where kind='sale'").fetchone()[0],333)
