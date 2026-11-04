"""Worker locale per l'esecuzione in sequenza degli scraper approvati.

Invocato dalla dashboard come processo separato per non bloccare Streamlit.
Non accetta percorsi arbitrari da HTTP o dalla UI.
"""
from __future__ import annotations

import os
import sys
import subprocess
import traceback
from pathlib import Path
from storage import BASE_DIR, DATABASE_PATH, connection, init_db, update_job

SCRIPTS_TRADE = [
    "1_certideal.py", "2_refurbed_it.py", "3_swappie.py",
    "4_compila_excel.py", "5_upload_xlsx_to_drive.py",
    "6_send_email_with_drive_link.py",
]

def find_repo(env_name, candidates, required):
    explicit = os.environ.get(env_name)
    paths = ([Path(explicit).expanduser()] if explicit else
             [BASE_DIR.parent / candidate for candidate in candidates])
    for path in paths:
        if (path / required).is_file():
            return path.resolve()
    raise FileNotFoundError(
        f"Repository non trovata ({env_name}): atteso {required}. "
        "Configura il percorso assoluto tramite la variabile d'ambiente."
    )

def python_for(repo):
    locations = [repo / ".venv" / "Scripts" / "python.exe", repo / ".venv" / "bin" / "python"]
    for path in locations:
        if path.is_file():
            return str(path)
    raise FileNotFoundError(f"Ambiente .venv non trovato in {repo}")

def commands(action):
    if action == "import_history":
        return [(str(Path(sys.executable).resolve()), BASE_DIR / "import_drive.py", BASE_DIR)]
    if action == "sale":
        repo = find_repo("WEFIX_SALES_REPO",
                         ["calcola_acquista_usato/calcola_acquista_usato", "calcola_acquista_usato"],
                         "scaper_trovaprezzi.py")
        return [(python_for(repo), repo / "scaper_trovaprezzi.py", repo)]
    if action == "trade_all" or action in {f"trade_{i}" for i in range(1,7)}:
        repo = find_repo("WEFIX_TRADE_REPO",
                         ["valuta_usato_platform","valutaUsato_platform"],
                         "scripts/1_certideal.py")
        scripts = SCRIPTS_TRADE if action == "trade_all" else [SCRIPTS_TRADE[int(action[-1]) - 1]]
        return [(python_for(repo), repo / "scripts" / name, repo) for name in scripts]
    raise ValueError("Azione non autorizzata")

def main(job_id):
    init_db()
    with connection() as db:
        row = db.execute("SELECT action,log_file FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Job inesistente")
    action, log_file = row["action"], Path(row["log_file"])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    status = "completed"
    exit_code = 0
    error = None
    update_job(job_id, status="running", pid=os.getpid())
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["WEFIX_DB_PATH"] = str(DATABASE_PATH.resolve())
    env["WEFIX_WEBAPP_HOME"] = str(BASE_DIR.resolve())
    try:
        with log_file.open("a", encoding="utf-8", errors="replace") as log:
            planned = commands(action)
            for step, (exe, script, cwd) in enumerate(planned,1):
                heading = f"\n{'='*70}\n{step}/{len(planned)} | {script.name}\nCWD={cwd}\nPYTHON={exe}\n{'='*70}\n"
                log.write(heading)
                log.flush()
                result = subprocess.run(
                    [exe, str(script)],
                    cwd=str(cwd), env=env,
                    stdout=log, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, check=False,
                )
                if result.returncode:
                    exit_code = result.returncode
                    status = "failed"
                    error = f"{script.name}: codice uscita {exit_code}"
                    break
    except Exception as exc:
        status = "failed"
        exit_code = 1
        error = str(exc)
        with log_file.open("a", encoding="utf-8") as log:
            log.write("\n"+traceback.format_exc())
    finally:
        update_job(job_id, status=status, exit_code=exit_code, pid=os.getpid(), error=error)
    return exit_code

if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        raise SystemExit("Uso: python job_runner.py <job_id>")
    raise SystemExit(main(int(sys.argv[1])))
