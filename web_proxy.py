"""Serve il frontend e inoltra solo le API dell'interfaccia al backend locale."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import mimetypes,os,hmac,hashlib,json,secrets,time,threading
from http.cookies import SimpleCookie

ROOT=Path(__file__).resolve().parent/'frontend'/'dist'
TOKEN=os.environ.get('WEFIX_API_TOKEN','')
CATALOG_TOKEN=os.environ.get('WEFIX_CATALOG_TOKEN','')
ADMIN_HASH=os.environ.get('WEFIX_PRICES_ADMIN_PASSWORD_SHA256','')
SESSIONS={}
SESSION_LOCK=threading.Lock()
SESSION_TTL=8*60*60
ALLOWED_GET={'/health','/snapshots','/prices','/history','/jobs'}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        path=urlsplit(self.path).path
        if path == '/api/wefix/session': return self.respond(200,json.dumps({'admin':self.is_admin()}).encode())
        if path in ('/api/catalog','/api/catalog/notifications'): return self.catalog('GET')
        if path.startswith('/api/wefix/'):
            return self.proxy('GET')
        if path=='/health':
            self.send_response(200);self.end_headers();self.wfile.write(b'ok');return
        relative='index.html' if path=='/' else path.lstrip('/')
        target=(ROOT/relative).resolve()
        if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
            self.send_error(404);return
        data=target.read_bytes();self.send_response(200)
        self.send_header('Content-Type',mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if urlsplit(self.path).path == '/api/catalog/action': return self.catalog('POST')
        origin=self.headers.get('Origin','')
        if not origin or urlsplit(origin).netloc != self.headers.get('Host',''):
            self.send_error(403);return
        path=urlsplit(self.path).path
        if path == '/api/wefix/login': return self.login()
        if path == '/api/wefix/logout': return self.logout()
        return self.proxy('POST')
    def is_admin(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return False
        token=cookie.get('wefix_prices_admin')
        if not token: return False
        with SESSION_LOCK:
            expiry=SESSIONS.get(token.value,0)
            if expiry <= time.time():
                SESSIONS.pop(token.value,None); return False
            return True
    def login(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size < 1 or size > 1024: raise ValueError()
            data=json.loads(self.rfile.read(size))
            username=data.get('username',''); password=data.get('password','')
            if not isinstance(username,str) or not isinstance(password,str): raise ValueError()
            valid=(len(ADMIN_HASH)==64 and hmac.compare_digest(username,'emanuele') and hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(),ADMIN_HASH))
        except (ValueError,TypeError,UnicodeError): valid=False
        if not valid: return self.respond(401,b'{"error":"Credenziali non valide"}')
        token=secrets.token_urlsafe(32)
        with SESSION_LOCK:
            now=time.time()
            for old,expiry in list(SESSIONS.items()):
                if expiry <= now: SESSIONS.pop(old,None)
            SESSIONS[token]=now+SESSION_TTL
        self.respond(200,b'{"admin":true}',f'wefix_prices_admin={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={SESSION_TTL}')
    def logout(self):
        cookie=SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie',''))
            token=cookie.get('wefix_prices_admin')
            if token:
                with SESSION_LOCK: SESSIONS.pop(token.value,None)
        except Exception: pass
        self.respond(200,b'{"admin":false}','wefix_prices_admin=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0')
    def catalog(self,method):
        if len(CATALOG_TOKEN)<32 or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+CATALOG_TOKEN):
            self.respond(401,b'{"error":"Non autorizzato"}'); return
        size=int(self.headers.get('Content-Length','0'))
        if size>128*1024: self.respond(413,b'{"error":"Richiesta troppo grande"}');return
        body=self.rfile.read(size) if method=='POST' else None
        path=self.path.removeprefix('/api')
        req=Request('http://127.0.0.1:8766'+path,data=body,method=method,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=30) as result: self.respond(result.status,result.read())
        except HTTPError as err: self.respond(err.code,err.read())
        except URLError: self.respond(503,b'{"error":"Servizio dati non disponibile"}')
    def proxy(self,method):
        path=self.path.removeprefix('/api/wefix'); route=urlsplit(path).path
        if (method=='POST' and route!='/jobs' and not (route.startswith('/jobs/') and route.endswith(('/continue','/challenge')))) or (method=='GET' and route not in ALLOWED_GET and not (route.startswith('/jobs/') and route.endswith(('/log','/challenge')))):
            self.send_error(404);return
        if (route == '/jobs' or route.startswith('/jobs/')) and not self.is_admin():
            return self.respond(401,b'{"error":"Accesso amministratore richiesto"}')
        size=int(self.headers.get('Content-Length','0'))
        if size>1024:self.send_error(413);return
        body=self.rfile.read(size) if method=='POST' else None
        req=Request('http://127.0.0.1:8766'+path,data=body,method=method,
                    headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=30) as result:
                self.respond(result.status,result.read())
        except HTTPError as err:
            self.respond(err.code,err.read())
        except URLError:
            self.respond(503,b'{"error":"Servizio dati non disponibile"}')
    def respond(self,code,data,cookie=None):
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    if len(TOKEN)<32: raise SystemExit('Token mancante')
    ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
