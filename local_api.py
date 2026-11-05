"""API locale per il frontend WeFix. Richiede un token anche su loopback."""
from __future__ import annotations
import hmac
import base64
import binascii
import json
import os
import subprocess
import sys
import time
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')
import storage
import price_catalog
import queue_store
from job_runner import SCRIPTS_TRADE

ACTIONS = {'sale', 'trade_all', 'import_history', *(f'trade_{i}' for i in range(1, 7))}

def records(frame):
    return json.loads(frame.to_json(orient='records', date_format='iso', force_ascii=False))

def launch(action):
    if action not in ACTIONS:
        raise ValueError('Comando non autorizzato')
    log = storage.BASE_DIR / 'data' / 'jobs' / f'{time.time_ns()}_{action}.log'
    job = storage.new_job(action, log)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    try:
        subprocess.Popen([sys.executable, str(storage.BASE_DIR / 'job_runner.py'), str(job)],
                         cwd=str(storage.BASE_DIR), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags, start_new_session=os.name != 'nt')
    except Exception as exc:
        storage.update_job(job, status='failed', exit_code=1, error=str(exc))
        raise
    return job

def handler_for(token, ingest_token=None, agent_token=None):
    ingest_token = token if ingest_token is None else ingest_token
    agent_token = token if agent_token is None else agent_token
    if any(not value or len(value) < 32 for value in (token,ingest_token,agent_token)):
        raise ValueError('I token WeFix devono contenere almeno 32 caratteri')
    agent_seen = [0.0]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, status, value):
            payload = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def authorised(self):
            path = urlsplit(self.path).path
            expected = ingest_token if path in ('/ingest','/ingest-rows') else agent_token if path.startswith('/agent/') else token
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + expected):
                self.reply(401, {'error': 'Non autorizzato'})
                return False
            return True
        def do_GET(self):
            if not self.authorised(): return
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == '/health':
                    return self.reply(200, {'ok': True, 'agent_online':bool(agent_seen[0]) and time.monotonic()-agent_seen[0] < 15})
                if parsed.path == '/snapshots':
                    return self.reply(200, records(storage.snapshots()))
                if parsed.path == '/prices':
                    kind = query.get('kind', [''])[0]
                    if kind not in ('sale','tradein'): raise ValueError('Tipo non valido')
                    return self.reply(200, records(storage.latest_prices(kind, query.get('sheet', [None])[0])))
                if parsed.path == '/catalog':
                    kind=query.get('kind',[''])[0]
                    storage.init_db()
                    with storage.connection() as db: result=price_catalog.list_catalog(db,kind)
                    return self.reply(200,result)
                if parsed.path == '/catalog/notifications':
                    actor=query.get('actor',[''])[0]
                    if not actor or len(actor)>40: raise ValueError('operatore non valido')
                    storage.init_db()
                    with storage.connection() as db: result=price_catalog.notifications(db,actor)
                    return self.reply(200,result)
                if parsed.path == '/history':
                    kind = query.get('kind', [''])[0]
                    if kind not in ('sale','tradein'): raise ValueError('Tipo non valido')
                    return self.reply(200, records(storage.history(kind, query['model'][0], int(query['storage'][0]), query.get('color',[None])[0], query.get('sheet',[None])[0])))
                if parsed.path == '/jobs':
                    return self.reply(200, records(storage.jobs().drop(columns=['log_file'], errors='ignore')))
                if parsed.path.startswith('/jobs/') and parsed.path.endswith('/log'):
                    job_id = int(parsed.path.split('/')[2])
                    with storage.connection() as db:
                        row = db.execute('SELECT log_file FROM jobs WHERE id=?', (job_id,)).fetchone()
                    if row is None: return self.reply(404, {'error':'Esecuzione non trovata'})
                    path = Path(row['log_file']).resolve()
                    root = (storage.BASE_DIR / 'data' / 'jobs').resolve()
                    if not path.is_relative_to(root): raise ValueError('Percorso log non valido')
                    if not path.is_file(): return self.reply(200, {'log':''})
                    with path.open('rb') as f:
                        f.seek(0, os.SEEK_END)
                        f.seek(max(0, f.tell()-32000))
                        output = f.read().decode('utf-8', errors='replace')
                    return self.reply(200, {'log':output})
                return self.reply(404, {'error':'Non trovato'})
            except (ValueError, KeyError):
                return self.reply(400, {'error':'Parametri non validi'})
        def do_POST(self):
            if not self.authorised(): return
            if self.path == '/catalog/action':
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=128*1024: raise ValueError('dimensione non valida')
                    body=json.loads(self.rfile.read(size)); actor=body.get('actor')
                    if not isinstance(actor,str) or not actor or len(actor)>40: raise ValueError('operatore non valido')
                    storage.init_db()
                    with storage.connection() as db:
                        action=body.get('action')
                        if action=='price': price_catalog.manual_price(db,body['price'],actor)
                        elif action=='rules': price_catalog.rules(db,body['kind'],body['mode'],body.get('up_limit'),body.get('down_limit'))
                        elif action=='decide': price_catalog.decide(db,body['ids'],body['decision'],actor)
                        elif action=='read': price_catalog.mark_read(db,actor,body['ids'])
                        else: raise ValueError('azione non valida')
                    return self.reply(200,{'ok':True})
                except (KeyError,TypeError,ValueError,json.JSONDecodeError): return self.reply(400,{'error':'Operazione non valida o proposta già modificata'})
            if self.path == '/ingest-rows':
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0 < size <= 4*1024*1024: raise ValueError('Dimensione non valida')
                    body=json.loads(self.rfile.read(size))
                    required={'rows','kind','source_id','filename','sheet_name','scanned_at','folder_name','source_url','is_primary'}
                    if not isinstance(body,dict) or set(body)!=required: raise ValueError('Dati non validi')
                    if body['kind'] not in ('sale','tradein') or type(body['is_primary']) is not bool: raise ValueError('Tipo non valido')
                    if any(not isinstance(body[k],str) or len(body[k])>2048 for k in required-{'rows','is_primary'}): raise ValueError('Metadati non validi')
                    if not isinstance(body['rows'],list) or len(body['rows'])>5000 or any(not isinstance(row,list) or len(row)>100 for row in body['rows']): raise ValueError('Righe non valide')
                    return self.reply(200,storage.import_rows(**body))
                except (KeyError,TypeError,ValueError,json.JSONDecodeError):
                    return self.reply(400,{'error':'Dati non validi'})
            if self.path.startswith('/agent/'):
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 128 * 1024: raise ValueError('Dimensione non valida')
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body, dict): raise ValueError('Richiesta non valida')
                    agent_seen[0] = time.monotonic()
                    if self.path == '/agent/claim' and not body:
                        return self.reply(200, {'job':queue_store.claim()})
                    if self.path == '/agent/log' and set(body) == {'id','text'} and type(body['id']) is int:
                        queue_store.append_log(body['id'], body['text'])
                        return self.reply(200, {'ok':True})
                    if self.path == '/agent/next-input' and set(body) == {'id'} and type(body['id']) is int:
                        return self.reply(200, {'continue':queue_store.take_continue(body['id'])})
                    if self.path == '/agent/finish' and set(body) == {'id','exit_code','error'} and type(body['id']) is int:
                        if body['error'] is not None and (not isinstance(body['error'], str) or len(body['error']) > 1024): raise ValueError('Errore non valido')
                        queue_store.finish(body['id'], body['exit_code'], body['error'])
                        return self.reply(200, {'ok':True})
                    raise ValueError('Richiesta non valida')
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    return self.reply(400, {'error':'Richiesta non valida'})
            if self.path == '/ingest':
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 24 * 1024 * 1024: raise ValueError('Dimensione non valida')
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body, dict) or set(body) - {'kind', 'filename', 'content', 'drive_url'}:
                        raise ValueError('Richiesta non valida')
                    kind, name = body['kind'], body['filename']
                    if kind not in ('sale', 'tradein') or not isinstance(name, str) or not name.lower().endswith('.xlsx'):
                        raise ValueError('File non valido')
                    if name in ('.', '..') or any(c in name for c in '/\\:') or len(name) > 180:
                        raise ValueError('Nome file non valido')
                    data = base64.b64decode(body['content'], validate=True)
                    if not data or len(data) > 16 * 1024 * 1024: raise ValueError('Dimensione non valida')
                    with tempfile.TemporaryDirectory() as tmp:
                        path = Path(tmp) / name
                        path.write_bytes(data)
                        result = storage.import_xlsx(path, kind=kind,
                            source_id=f'local:{kind}:{name}', source_url=body.get('drive_url', ''), folder_name='API')
                    return self.reply(200, result)
                except (KeyError, TypeError, ValueError, binascii.Error, json.JSONDecodeError):
                    return self.reply(400, {'error':'File o richiesta non validi'})
            if self.path.startswith('/jobs/') and self.path.endswith('/continue'):
                try:
                    parts=self.path.split('/')
                    if len(parts)!=4 or not parts[2].isdigit(): raise ValueError('Esecuzione non valida')
                    size=int(self.headers.get('Content-Length','0'))
                    if size != 2 or self.rfile.read(size) != b'{}': raise ValueError('Richiesta non valida')
                    queue_store.request_continue(int(parts[2]))
                    return self.reply(200,{'ok':True})
                except (TypeError,ValueError):
                    return self.reply(400,{'error':'Esecuzione non attiva'})
            if self.path != '/jobs': return self.reply(404, {'error':'Non trovato'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024: raise ValueError('Richiesta non valida')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) != {'action'} or not isinstance(body['action'], str): raise ValueError('Richiesta non valida')
                job = queue_store.enqueue(body['action']) if os.environ.get('WEFIX_QUEUE_ENABLED') == '1' else launch(body['action'])
                return self.reply(201, {'id':job})
            except RuntimeError as exc:
                return self.reply(409, {'error':str(exc)})
            except (ValueError, json.JSONDecodeError):
                return self.reply(400, {'error':'Richiesta non valida'})
    return Handler

def main():
    token = os.environ.get('WEFIX_API_TOKEN', '')
    ingest_token = os.environ.get('WEFIX_DB_API_TOKEN', '')
    agent_token = os.environ.get('WEFIX_AGENT_TOKEN', '')
    if len({token,ingest_token,agent_token}) != 3:
        raise ValueError('Servono tre token distinti per interfaccia, inserimento e agente')
    storage.init_db()
    server = ThreadingHTTPServer((os.environ.get('WEFIX_API_BIND', '127.0.0.1'), int(os.environ.get('WEFIX_API_PORT','8766'))), handler_for(token,ingest_token,agent_token))
    server.serve_forever()

if __name__ == '__main__': main()
