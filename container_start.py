import signal, subprocess, sys, time
from migration_restore import restore
restore()
children=[]
def stop(*_):
    for child in children:
        if child.poll() is None: child.terminate()
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
children.append(subprocess.Popen([sys.executable,'local_api.py']))
children.append(subprocess.Popen([sys.executable,'web_proxy.py']))
try:
    while all(child.poll() is None for child in children):
        time.sleep(1)
finally:stop()
sys.exit(1)
