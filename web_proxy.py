"""Serve il frontend e inoltra solo le API dell'interfaccia al backend locale."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import mimetypes,os

ROOT=Path(__file__).resolve().parent/'frontend'/'dist'
TOKEN=os.environ.get('WEFIX_API_TOKEN','')
ALLOWED_GET={'/health','/snapshots','/prices','/history','/jobs'}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        path=urlsplit(self.path).path
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
        origin=self.headers.get('Origin','')
        if not origin or urlsplit(origin).netloc != self.headers.get('Host',''):
            self.send_error(403);return
        return self.proxy('POST')
    def proxy(self,method):
        path=self.path.removeprefix('/api/wefix'); route=urlsplit(path).path
        if (method=='POST' and route!='/jobs' and not (route.startswith('/jobs/') and route.endswith('/continue'))) or (method=='GET' and route not in ALLOWED_GET and not (route.startswith('/jobs/') and route.endswith('/log'))):
            self.send_error(404);return
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
    def respond(self,code,data):
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    if len(TOKEN)<32: raise SystemExit('Token mancante')
    ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
