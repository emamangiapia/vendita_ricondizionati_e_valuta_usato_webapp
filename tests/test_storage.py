"""Test delle importazioni: nessuna rete né credenziale richiesta."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get("WEFIX_DB_PATH")
        os.environ["WEFIX_DB_PATH"] = str(Path(self.tmp.name) / "prices.sqlite3")
        import storage
        self.storage = importlib.reload(storage)
        self.storage.init_db()

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("WEFIX_DB_PATH", None)
        else:
            os.environ["WEFIX_DB_PATH"] = self.previous
        self.tmp.cleanup()

    def test_prices_parse_in_italian_format(self):
        s = self.storage
        self.assertEqual(s.parse_price("€ 1.299,90"),1299.90)
        self.assertEqual(s.parse_price("1,299.90 €"),1299.90)
        self.assertEqual(s.parse_price("704.99"),704.99)
        self.assertIsNone(s.parse_price("inesistente"))
        self.assertIsNone(s.parse_price(""))
        self.assertIsNone(s.parse_price(None))
        self.assertEqual(s.storage_to_gb("2 TB"),2048)
        self.assertEqual(s.storage_to_gb("256 GB"),256)

    def test_timestamp_folder_formats(self):
        s = self.storage
        self.assertEqual(s.parse_scanned_at("run_20261030_113056"),"2026-10-30T11:30:56")
        self.assertEqual(s.parse_scanned_at("2026-10-31_18-38-21"),"2026-10-31T18:38:21")
        self.assertEqual(s.parse_scanned_at("prezzi_del_21-02-2025_20-03-49"),"2025-02-21T20:03:49")

    def test_idempotent_import_detects_same_count_price_change(self):
        s=self.storage
        rows=[
          ["","Modello","Colori","512 GB","256 GB"],
          ["0","Aggiornato il: 30/10/2026 11:30:56","","",""],
          [1,"iPhone 17 Pro","Argento","€ 1.082,99",936.98],
          [2,"iPhone 17 Pro","Arancione cosmico","inesistente",936.98],
        ]
        kwargs=dict(kind="sale",source_id="file001",filename="a.xlsx",sheet_name="Apple",
                    scanned_at="2026-10-30T11:30:56",is_primary=True)
        self.assertEqual(s.import_rows(rows,**kwargs)["count"],3)
        self.assertEqual(s.import_rows(rows,**kwargs)["status"],"skipped")
        df=s.latest_prices("sale")
        self.assertEqual(len(df),3)
        rows[2][4]=900.0
        self.assertEqual(s.import_rows(rows,**kwargs)["status"],"imported")
        df=s.latest_prices("sale")
        self.assertEqual(float(df[(df.color=="Argento") & (df.storage_gb==256)].iloc[0].price_eur),900.0)
        self.assertEqual(len(s.snapshots()),1)

    def test_tradein_two_line_header(self):
        s=self.storage
        rows=[
          ["Data e ora di estrazione: 31/10/2026 18:38",None,None,None],
          ["Modello","Colori","512 GB","256 GB"],
          ["iPhone 17 Pro","Blu profondo",770,765],
          ["iPhone 17 Pro","Argento","inesistente","765"],
        ]
        kwargs=dict(kind="tradein",source_id="filetrade",filename="BE.xlsx",
                    sheet_name="Apple",scanned_at="2026-10-31T18:38:21",is_primary=True)
        self.assertEqual(s.import_rows(rows,**kwargs)["count"],3)
        self.assertEqual(len(s.latest_prices("tradein")),3)

    def test_all_worksheets_stored_without_mixing_primary(self):
        from openpyxl import Workbook
        s=self.storage
        path=Path(self.tmp.name)/"Prezzi_ValutaUsato_2026-10-31_18-38-21.xlsx"
        wb=Workbook()
        apple=wb.active
        apple.title="Apple"
        apple.append(["Modello","Colori","256 GB"])
        apple.append(["iPhone 15","Nero",340])
        merchant=wb.create_sheet("swappie.com")
        merchant.append(["Modello","Colori","256 GB"])
        merchant.append(["iPhone 15","Nero",320])
        wb.save(path)
        result=s.import_xlsx(path,kind="tradein")
        self.assertEqual(result["sheets"],2)
        self.assertEqual(len(s.snapshots()),2)
        self.assertEqual(s.latest_prices("tradein").iloc[0].price_eur,340)
        self.assertEqual(s.latest_prices("tradein","swappie.com").iloc[0].price_eur,320)

if __name__ == "__main__":
    unittest.main()
