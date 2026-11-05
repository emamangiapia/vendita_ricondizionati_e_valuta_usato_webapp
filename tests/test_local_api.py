import http.client
import base64
import io
import json
import tempfile
import threading
import sys
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import storage
from local_api import handler_for

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = storage.DATABASE_PATH
        self.base = storage.BASE_DIR
        storage.BASE_DIR = Path(self.temp.name)
        storage.DATABASE_PATH = Path(self.temp.name) / 'test.sqlite3'
        storage.init_db()
        self.token = 'x' * 32
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        storage.DATABASE_PATH = self.db
        storage.BASE_DIR = self.base
        self.temp.cleanup()
    def request(self, method, path, body=None, token=None):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Authorization':'Bearer '+token} if token else {}
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse(); data = json.loads(r.read()); c.close()
        return r.status, data
    def test_requires_token_and_rejects_unlisted_command(self):
        self.assertEqual(self.request('GET','/snapshots')[0],401)
        self.assertEqual(self.request('GET','/snapshots',token='wrong')[0],401)
        self.assertEqual(self.request('GET','/snapshots',token=self.token),(200,[]))
        with patch('local_api.subprocess.Popen') as spawn:
            self.assertEqual(self.request('POST','/jobs',body='{"action":"arbitrary"}',token=self.token)[0],400)
            spawn.assert_not_called()
    def test_rejects_short_token(self):
        with self.assertRaises(ValueError): handler_for('short')

    def test_credentials_are_scoped_to_each_role(self):
        ingest_token = 'i' * 32
        agent_token = 'a' * 32
        self.server.RequestHandlerClass = handler_for(self.token, ingest_token, agent_token)
        self.assertEqual(self.request('GET','/jobs',token=ingest_token)[0],401)
        self.assertEqual(self.request('GET','/jobs',token=agent_token)[0],401)
        self.assertEqual(self.request('POST','/agent/claim',body='{}',token=ingest_token)[0],401)
        self.assertEqual(self.request('POST','/agent/claim',body='{}',token=self.token)[0],401)
        self.assertEqual(self.request('POST','/ingest',body='{}',token=self.token)[0],401)
        self.assertFalse(self.request('GET','/health',token=self.token)[1]['agent_online'])
        self.assertEqual(self.request('POST','/agent/claim',body='{}',token=agent_token)[0],200)
        self.assertTrue(self.request('GET','/health',token=self.token)[1]['agent_online'])

    def test_ingest_requires_token_and_is_idempotent(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Apple'
        ws.append(['Modello', 'Colore', '128 GB'])
        ws.append(['iPhone 15', 'Nero', 250])
        buf = io.BytesIO(); wb.save(buf)
        body = json.dumps({'kind':'sale', 'filename':'run_20261104_120000.xlsx',
                           'content':base64.b64encode(buf.getvalue()).decode('ascii')})
        self.assertEqual(self.request('POST', '/ingest', body=body)[0], 401)
        status, result = self.request('POST', '/ingest', body=body, token=self.token)
        self.assertEqual((status, result['status'], result['count']), (200, 'imported', 1))
        status, result = self.request('POST', '/ingest', body=body, token=self.token)
        self.assertEqual((status, result['status']), (200, 'skipped'))

    def test_scraper_ingest_client_reaches_api(self):
        from openpyxl import Workbook
        from ingest import send_xlsx
        wb = Workbook(); ws = wb.active
        ws.append(['Modello', 'Colore', '128 GB']); ws.append(['iPhone 15', 'Nero', 180])
        path = Path(self.temp.name) / '20261104_120000.xlsx'; wb.save(path)
        env = {'WEFIX_DB_API_URL':f'http://127.0.0.1:{self.server.server_port}',
               'WEFIX_DB_API_TOKEN':self.token}
        with patch.dict('os.environ', env):
            result = send_xlsx(path, 'tradein')
        self.assertEqual((result['status'], result['count']), ('imported', 1))
        self.assertEqual(len(storage.latest_prices('tradein')), 1)

    def test_historical_rows_preserve_source_and_sheet(self):
        from ingest import post_api
        payload={'rows':[['Modello','Colore','128 GB'],['iPhone','Nero',200]],
                 'kind':'sale','source_id':'drive-id','filename':'listino',
                 'sheet_name':'Apple','scanned_at':'2025-01-01T00:00:00',
                 'folder_name':'2025-01-01','source_url':'https://drive.google.com/', 'is_primary':True}
        env={'WEFIX_DB_API_URL':f'http://127.0.0.1:{self.server.server_port}', 'WEFIX_DB_API_TOKEN':self.token}
        with patch.dict('os.environ',env):
            self.assertEqual(post_api('/ingest-rows',payload)['status'],'imported')
            self.assertEqual(post_api('/ingest-rows',payload)['status'],'skipped')
        self.assertEqual(storage.snapshots().iloc[0].source_id,'drive-id')

    def test_agent_executes_only_queued_test_script(self):
        import windows_agent
        with patch.dict('os.environ', {'WEFIX_QUEUE_ENABLED':'1'}):
            status, created = self.request('POST','/jobs',body='{"action":"trade_1"}',token=self.token)
            self.assertEqual(status,201)
            status, response = self.request('POST','/agent/claim',body='{}',token=self.token)
            self.assertEqual(response['job']['id'], created['id'])
            script=Path(self.temp.name)/'fixture.py'
            script.write_text("print('esecuzione simulata')\n",encoding='utf-8')
            endpoint=f'http://127.0.0.1:{self.server.server_port}'
            with patch.object(windows_agent,'URL',endpoint), patch.object(windows_agent,'TOKEN',self.token), \
                 patch.object(windows_agent,'commands',return_value=[(sys.executable,script,Path(self.temp.name))]):
                windows_agent.run(response['job'])
            status, jobs = self.request('GET','/jobs',token=self.token)
            self.assertEqual(jobs[0]['status'],'completed')
            status, log = self.request('GET',f"/jobs/{created['id']}/log",token=self.token)
            self.assertIn('esecuzione simulata',log['log'])

    def test_agent_can_continue_an_interactive_script(self):
        import windows_agent
        with patch.dict('os.environ', {'WEFIX_QUEUE_ENABLED':'1'}):
            _, created=self.request('POST','/jobs',body='{"action":"sale"}',token=self.token)
            _, response=self.request('POST','/agent/claim',body='{}',token=self.token)
            script=Path(self.temp.name)/'interactive.py'
            script.write_text("print('Premi INVIO',flush=True)\ninput()\nprint('proseguito',flush=True)\n",encoding='utf-8')
            with patch.object(windows_agent,'URL',f'http://127.0.0.1:{self.server.server_port}'), \
                 patch.object(windows_agent,'TOKEN',self.token), \
                 patch.object(windows_agent,'commands',return_value=[(sys.executable,script,Path(self.temp.name))]):
                thread=threading.Thread(target=windows_agent.run,args=(response['job'],),daemon=True);thread.start()
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    _, result=self.request('GET',f"/jobs/{created['id']}/log",token=self.token)
                    if 'Premi INVIO' in result['log']: break
                    time.sleep(.1)
                self.assertIn('Premi INVIO',result['log'])
                self.assertEqual(self.request('POST',f"/jobs/{created['id']}/continue",body='{}',token=self.token)[0],200)
                thread.join(timeout=10)
                self.assertFalse(thread.is_alive())
                _, result=self.request('GET',f"/jobs/{created['id']}/log",token=self.token)
                self.assertIn('proseguito',result['log'])

if __name__ == '__main__': unittest.main()
