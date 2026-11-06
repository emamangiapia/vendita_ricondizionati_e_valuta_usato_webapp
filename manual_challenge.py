"""Runs in the scraper's Playwright thread, only during a manual challenge."""
import base64
import json
import os
import time
from urllib.request import Request, urlopen

def wait_for_verification(page):
    endpoint = os.environ.get('WEFIX_CHALLENGE_API')
    token = os.environ.get('WEFIX_CHALLENGE_TOKEN')
    job_id = int(os.environ.get('WEFIX_CHALLENGE_JOB', '0'))
    if not endpoint or not token or not job_id:
        input('Premi INVIO dopo aver risolto la verifica...')
        return
    def publish(frame):
        body = json.dumps({'id': job_id, 'frame': frame}).encode()
        req = Request(endpoint+'/agent/challenge', data=body,
                      headers={'Authorization':'Bearer '+token, 'Content-Type':'application/json'})
        with urlopen(req, timeout=10) as response: return json.load(response)['events']
    print('Verifica manuale disponibile nella webapp WeFix Prices.', flush=True)
    try:
        while not page.is_closed():
            try:
                frame = base64.b64encode(page.screenshot(type='jpeg', quality=65)).decode()
                for event in publish(frame):
                    size = page.viewport_size or page.evaluate('({width:innerWidth,height:innerHeight})')
                    kind = event['type']
                    if kind == 'continue': return
                    if kind in ('move','down','up'):
                        page.mouse.move(event['x']*size['width'], event['y']*size['height'])
                        if kind == 'down': page.mouse.down()
                        if kind == 'up': page.mouse.up()
                    elif kind == 'text': page.keyboard.insert_text(event['text'])
                    elif kind == 'key': page.keyboard.press(event['key'])
            except Exception as exc:
                print('Collegamento verifica temporaneamente non disponibile: '+type(exc).__name__, flush=True)
            page.wait_for_timeout(250)
    finally:
        try: page.mouse.up()
        except Exception: pass
        try: publish(None)
        except Exception: pass
