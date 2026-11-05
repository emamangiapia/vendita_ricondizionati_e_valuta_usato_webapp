"""Agente Windows: preleva i job autorizzati e avvia gli script locali."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from dotenv import load_dotenv
load_dotenv(os.environ.get('WEFIX_AGENT_ENV') or Path(__file__).resolve().parent / '.env')
from job_runner import commands

URL = os.environ.get('WEFIX_DB_API_URL', '').rstrip('/')
TOKEN = os.environ.get('WEFIX_AGENT_TOKEN', '')

def post(route, body):
    target = urlsplit(URL)
    if (target.scheme != 'https' and not (target.scheme == 'http' and target.hostname in ('127.0.0.1','localhost','::1'))) or not target.netloc:
        raise ValueError('API agente richiede HTTPS o loopback')
    if len(TOKEN) < 32: raise ValueError('Token agente mancante o troppo corto')
    payload = json.dumps(body,ensure_ascii=False).encode('utf-8')
    req = Request(URL + route, data=payload, headers={'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},method='POST')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl): return None
    with build_opener(NoRedirect).open(req,timeout=30) as response: return json.load(response)

def run(job):
    job_id,action = job['id'],job['action']
    result_code=0; error=None; log_error=False
    env=os.environ.copy(); env['PYTHONUNBUFFERED']='1';env['PYTHONIOENCODING']='utf-8'
    env.pop('WEFIX_AGENT_TOKEN',None);env.pop('WEFIX_API_TOKEN',None)
    env['WEFIX_WEBAPP_HOME']=str(Path(__file__).resolve().parent)
    try:
        for index,(exe,script,cwd) in enumerate(commands(action),1):
            post('/agent/log',{'id':job_id,'text':f'\n{index} | {script.name}\n'})
            child=subprocess.Popen([exe,str(script)],cwd=str(cwd),env=env,stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=1,
                                   text=True,encoding='utf-8',errors='replace')
            stop=threading.Event()
            def feed_input():
                while not stop.wait(2):
                    try:
                        if child.poll() is None and post('/agent/next-input',{'id':job_id})['continue']:
                            child.stdin.write('\n');child.stdin.flush()
                    except Exception:
                        pass
            feeder=threading.Thread(target=feed_input,daemon=True);feeder.start()
            assert child.stdout is not None
            try:
                with child.stdout:
                    for line in child.stdout:
                        try:
                            post('/agent/log',{'id':job_id,'text':line[:32000]})
                        except Exception:
                            # Continuare a consumare stdout evita di bloccare lo script.
                            log_error=True
                result_code=child.wait()
            finally:
                stop.set();feeder.join(timeout=3)
                if child.stdin: child.stdin.close()
            if result_code:
                error=f'{script.name}: codice uscita {result_code}'
                break
    except Exception as exc:
        result_code=1;error=str(exc)[:1024]
    if log_error and result_code == 0:
        result_code=1;error='Script terminato, ma alcune righe del log non sono state consegnate.'
    while True:
        try:
            post('/agent/finish',{'id':job_id,'exit_code':result_code,'error':error})
            break
        except Exception:
            print('[WEFIX AGENTE] In attesa di comunicare l’esito al server.',flush=True)
            time.sleep(5)

def main():
    while True:
        try:
            job=post('/agent/claim',{})['job']
            if job: run(job)
            else:
                # La supervisione puo' aggiornare l'agente solo quando e' inattivo.
                release_file=os.environ.get('WEFIX_RELEASE_STATE')
                expected=os.environ.get('WEFIX_RELEASE_SHA')
                if release_file and expected:
                    try:
                        state=json.loads(Path(release_file).read_text(encoding='utf-8'))
                        current=state.get('wefix-prices',{}).get('deployed')
                        if isinstance(current,str) and current and current != expected:
                            return
                    except (OSError,ValueError):
                        pass
                time.sleep(2)
        except Exception as exc:
            print(f'[WEFIX AGENTE] {type(exc).__name__}: collegamento non disponibile',flush=True)
            time.sleep(5)

if __name__ == '__main__': main()
