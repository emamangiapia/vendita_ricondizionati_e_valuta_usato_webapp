"""Transient manual browser interaction, restricted to running jobs."""
import base64
import threading
import time
import storage

LOCK = threading.Lock()
STATE = {}

def running(job_id):
    if type(job_id) is not int:
        raise ValueError('Esecuzione non valida')
    with storage.connection() as db:
        if not db.execute("SELECT 1 FROM jobs WHERE id=? AND status='running'", (job_id,)).fetchone():
            raise ValueError('Esecuzione non attiva')

def publish(job_id, frame):
    running(job_id)
    if frame is not None:
        if not isinstance(frame, str) or len(frame) > 1500000:
            raise ValueError('Immagine non valida')
        data = base64.b64decode(frame, validate=True)
        if not data.startswith(b'\xff\xd8'):
            raise ValueError('Formato non valido')
    with LOCK:
        if frame is None:
            STATE.pop(job_id, None)
            return []
        old = STATE.get(job_id, {})
        events = old.get('events', [])
        STATE.clear()  # the agent runs only one browser job at a time
        STATE[job_id] = {'frame': frame, 'seen': time.monotonic(), 'events': []}
        return events

def read(job_id):
    running(job_id)
    with LOCK:
        item = STATE.get(job_id)
        return {'active': bool(item and time.monotonic()-item['seen'] < 15),
                'frame': item['frame'] if item and time.monotonic()-item['seen'] < 15 else None}

def input_event(job_id, event):
    running(job_id)
    if not isinstance(event, dict): raise ValueError('Comando non valido')
    kind = event.get('type')
    if kind in ('move', 'down', 'up'):
        if set(event) != {'type','x','y'} or any(type(event[k]) not in (int,float) or not 0 <= event[k] <= 1 for k in ('x','y')):
            raise ValueError('Coordinate non valide')
    elif kind == 'key':
        if set(event) != {'type','key'} or event['key'] not in ('Tab','Enter','Space','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Backspace'):
            raise ValueError('Tasto non valido')
    elif kind == 'text':
        if set(event) != {'type','text'} or not isinstance(event['text'], str) or not 1 <= len(event['text']) <= 100 or any(ord(c) < 32 for c in event['text']):
            raise ValueError('Testo non valido')
    elif kind == 'continue':
        if set(event) != {'type'}: raise ValueError('Comando non valido')
    else: raise ValueError('Comando non valido')
    with LOCK:
        item = STATE.get(job_id)
        if not item or time.monotonic()-item['seen'] >= 15: raise ValueError('Verifica non disponibile')
        if len(item['events']) >= 200: raise ValueError('Attendi un istante')
        item['events'].append(event)
