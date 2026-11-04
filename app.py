"""WeFix | dashboard locale per il mercato ricondizionati e valutazioni usato."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import pandas as pd
import streamlit as st
from storage import (
    BASE_DIR, DATABASE_PATH, init_db, latest_prices, history, snapshots, jobs,
    new_job, update_job
)

st.set_page_config(page_title="WeFix | Price Intelligence",
                   page_icon="📱", layout="wide", initial_sidebar_state="expanded")
# Streamlit non usa componenti React: applichiamo i token del kit ai widget nativi.
style = (Path(__file__).resolve().parent / "assets" / "wefix-streamlit.css").read_text(encoding="utf-8-sig")
st.markdown(f"<style>{style}</style>", unsafe_allow_html=True)

init_db()

def money(v):
    return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def date_short(value):
    return str(value).replace("T", " ")[:16] if value else "N/D"

def load_latest(kind, sheet=None):
    return latest_prices(kind, sheet_name=sheet)

def start(action):
    allowed = {"sale", "trade_all", "import_history",
               "trade_1","trade_2","trade_3","trade_4","trade_5","trade_6"}
    if action not in allowed:
        raise ValueError("Azione non autorizzata")
    logfile = BASE_DIR / "data" / "jobs" / f"{int(time.time()*1000)}_{action}.log"
    try:
        job_id = new_job(action, logfile)
    except RuntimeError as exc:
        st.warning(f"{exc} Attendi il completamento e controlla stato e log nel registro dei processi in fondo alla pagina.")
        return
    st.session_state["live_job_id"] = job_id
    st.session_state["live_job_action"] = action
    cmd = [sys.executable, str(BASE_DIR / "job_runner.py"), str(job_id)]
    kwargs = {"cwd":str(BASE_DIR), "stdin":subprocess.DEVNULL,
              "stdout":subprocess.DEVNULL, "stderr":subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kwargs)
        st.success(f"Esecuzione avviata, job #{job_id}. Il log compare qui sotto.")
    except Exception as exc:
        update_job(job_id,status="failed",exit_code=1,error=str(exc))
        st.error(f"Avvio non riuscito: {exc}")


@st.fragment(run_every="2s")
def live_log(job_id):
    """Aggiorna solo il pannello del job, senza rilanciare i pulsanti."""
    records = jobs()
    selected = records[records.id == job_id]
    if selected.empty:
        st.warning("Esecuzione non trovata nel registro.")
        return
    row = selected.iloc[0]
    labels = {"queued": "In attesa", "running": "In corso", "completed": "Completata", "failed": "Fallita"}
    status = str(row.status)
    st.markdown(f"**Esecuzione #{job_id} · {labels.get(status, status)}**")
    if status in ("queued", "running"):
        st.caption("Aggiornamento automatico ogni 2 secondi · ultime righe del log")
    elif status == "failed":
        detail = row.error if pd.notna(row.error) and row.error else "consulta il log per i dettagli"
        st.error(f"Esecuzione fallita: {detail}")
    else:
        st.caption("Esecuzione terminata · ultime righe del log")
    path = Path(str(row.log_file))
    if path.is_file():
        with path.open("rb") as log:
            log.seek(0, os.SEEK_END)
            log.seek(max(0, log.tell() - 16000))
            text = log.read().decode("utf-8", errors="replace")
        st.code("\n".join(text.splitlines()[-15:]) or "In attesa dei primi messaggi…", language=None, height=300)
    else:
        st.info("In attesa dei primi messaggi del processo…")


def show_live_log(*actions):
    if st.session_state.get("live_job_action") in actions:
        live_log(st.session_state["live_job_id"])

def view_prices(kind):
    available = snapshots()
    available = available[available.kind == kind]
    sheets = available.sheet_name.drop_duplicates().tolist() if not available.empty else []
    sheets = sorted(sheets, key=lambda x:(x.casefold() != "apple", x))
    chosen_sheet = st.selectbox("Fonte o indicatore del prezzo", sheets, index=0) if sheets else None
    items = load_latest(kind, chosen_sheet)
    if items.empty:
        st.info("Nessun dato importato. Nella scheda Esecuzioni premi 'Importa storico Drive'.")
        return
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Prezzi disponibili",f"{len(items):,}".replace(",","." ))
    c2.metric("Modelli",items["model_key"].nunique())
    c3.metric("Prezzo mediano",money(items.price_eur.median()))
    c4.metric("Ultima rilevazione",date_short(items.scanned_at.max()))
    st.write("")
    left,mid,right = st.columns([2,1,2])
    models = sorted(items.model.unique())
    model = left.selectbox("Modello", models, index=0)
    opts = items[items.model == model]
    storage_options = sorted(opts.storage_gb.unique(),reverse=True)
    gb = mid.selectbox("Memoria", storage_options,format_func=lambda x:f"{x//1024} TB" if x>=1024 else f"{x} GB")
    opts = opts[opts.storage_gb == gb]
    colors = ["Tutti i colori"] + sorted(opts.color.unique())
    color = right.selectbox("Colore", colors)
    subset = opts if color == "Tutti i colori" else opts[opts.color == color]
    st.subheader("Listino corrente")
    data = subset[["model","color","storage_gb","price_eur","scanned_at","filename"]].rename(columns={
        "model":"Modello","color":"Colore","storage_gb":"Memoria (GB)",
        "price_eur":"Prezzo (€)","scanned_at":"Rilevazione","filename":"File di origine"
    })
    st.dataframe(data,hide_index=True,use_container_width=True,
                 column_config={"Prezzo (€)":st.column_config.NumberColumn(format="%.2f €")})
    st.download_button("Esporta listino filtrato (CSV)",data.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"wefix_{kind}_prezzi.csv",mime="text/csv")
    if color != "Tutti i colori":
        series = history(kind,opts.iloc[0].model_key,gb,subset.iloc[0].color_key,sheet_name=chosen_sheet)
    else:
        series = history(kind,opts.iloc[0].model_key,gb,sheet_name=chosen_sheet)
        if not series.empty:
            series = series.groupby("scanned_at",as_index=False)["price_eur"].median()
    if not series.empty:
        st.subheader("Evoluzione nel tempo")
        chart = series[["scanned_at","price_eur"]].copy()
        chart["scanned_at"] = pd.to_datetime(chart["scanned_at"],errors="coerce")
        chart = chart.dropna(subset=["scanned_at"]).set_index("scanned_at")
        st.line_chart(chart,y="price_eur",x_label="Data rilevazione",y_label="Euro",height=310)
        st.caption("Dati storici di estrazione. Il valore mostrato dipende dal foglio Apple scelto nell'importazione.")

def comparison():
    sale = load_latest("sale")
    buy = load_latest("tradein")
    if sale.empty or buy.empty:
        st.info("Il confronto sarà disponibile dopo aver importato entrambe le fonti Drive.")
        return
    keys = ["model_key","color_key","storage_gb"]
    joined = sale.merge(buy,on=keys,how="inner",suffixes=("_sale","_trade"))
    if joined.empty:
        st.warning("Nessuna combinazione modello, colore e memoria identica nelle due fonti.")
        return
    joined["spread_eur"] = (joined.price_eur_sale-joined.price_eur_trade).round(2)
    joined["spread_pct"] = (joined.spread_eur/joined.price_eur_sale*100).round(1)
    a,b,c = st.columns(3)
    a.metric("Configurazioni confrontabili",len(joined))
    b.metric("Spread mediano",money(joined.spread_eur.median()))
    c.metric("Differenziale mediano",f"{joined.spread_pct.median():.1f}%")
    st.caption("Lo spread è il prezzo vendita meno la valutazione usato. Non è un margine netto e non considera costi, IVA o condizioni.")
    models = sorted(joined.model_sale.unique())
    selected = st.multiselect("Filtra per modello",models,default=[])
    if selected:
        joined=joined[joined.model_sale.isin(selected)]
    output=joined[["model_sale","color_sale","storage_gb","price_eur_sale",
                   "price_eur_trade","spread_eur","spread_pct",
                   "scanned_at_sale","scanned_at_trade"]].rename(columns={
        "model_sale":"Modello","color_sale":"Colore","storage_gb":"Memoria (GB)",
        "price_eur_sale":"Prezzo vendita (€)","price_eur_trade":"Valutazione usato (€)",
        "spread_eur":"Spread (€)","spread_pct":"Spread (%)",
        "scanned_at_sale":"Data vendita","scanned_at_trade":"Data valutazione"
    })
    st.dataframe(output.sort_values("Spread (€)",ascending=False),
                 hide_index=True,use_container_width=True)
    st.download_button("Esporta confronto (CSV)",output.to_csv(index=False).encode("utf-8-sig"),
                       "wefix_comparazione.csv","text/csv")

def historical():
    df=snapshots()
    if df.empty:
        st.info("Lo storico è vuoto.")
        return
    a,b,c=st.columns(3)
    a.metric("Scarichi archiviati",df[["kind","source_id"]].drop_duplicates().shape[0])
    b.metric("Listini vendita",df[df.kind=="sale"].source_id.nunique())
    c.metric("Listini usato",df[df.kind=="tradein"].source_id.nunique())
    category=st.radio("Tipologia",["Tutte","Vendita ricondizionati","Valuta usato"],horizontal=True)
    if category!="Tutte":
        df=df[df.kind==("sale" if category=="Vendita ricondizionati" else "tradein")]
    st.dataframe(df.rename(columns={
        "kind":"Tipo","scanned_at":"Data scarico","filename":"File",
        "folder_name":"Cartella Drive","sheet_name":"Foglio","source_id":"ID sorgente",
        "is_primary":"Principale",
        "record_count":"Prezzi letti","source_url":"Link origine","imported_at":"Importato il"
    }),hide_index=True,use_container_width=True,
        column_config={"Link origine":st.column_config.LinkColumn("Link origine")})
    st.download_button("Esporta catalogo degli scarichi",df.to_csv(index=False).encode("utf-8-sig"),
                       "wefix_archivio_scarichi.csv","text/csv")
    st.caption("Ogni riga rappresenta un listino importato. Gli originali restano su Google Drive.")

def executions():
    st.subheader("Ricondizionati")
    st.write("Avvia **scaper_trovaprezzi.py** tramite la .venv della sua repository. Al termine crea Excel, carica su Drive e aggiorna SQLite.")
    if st.button("Avvia scraper vendita ricondizionati",type="primary",key="sale"):
        start("sale")
    show_live_log("sale")
    st.divider()
    st.subheader("Valuta usato")
    steps=[
        ("1. CertiDeal","trade_1"),("2. Refurbed.it","trade_2"),("3. Swappie","trade_3"),
        ("4. Compila Excel","trade_4"),("5. Carica su Google Drive e salva DB","trade_5"),
        ("6. Invia email","trade_6"),
    ]
    for i in range(0,6,3):
        cols=st.columns(3)
        for col,(label,action) in zip(cols,steps[i:i+3]):
            with col:
                if st.button(label,key=action,use_container_width=True):
                    start(action)
        show_live_log(*(action for _, action in steps[i:i+3]))
    st.write("La pipeline completa si interrompe al primo errore. Lo step 5 aggiorna il database e lo step 6 mantiene l'invio email esistente.")
    if st.button("Avvia tutta la pipeline usato (1 → 6)",type="primary",key="trade_all"):
        start("trade_all")
    show_live_log("trade_all")
    st.divider()
    st.subheader("Importa tutti gli scarichi storici")
    st.write("Importa entrambi gli archivi Drive, conserva le date e ignora i file già acquisiti. Richiede credenziali locali.")
    if st.button("Importa storico Drive",key="import_history"):
        start("import_history")
    show_live_log("import_history")
    st.caption("Credentials: "+("configurate" if os.getenv("WEFIX_GOOGLE_CREDENTIALS") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS") else "rilevamento automatico nei progetti esistenti"))
    st.divider()
    st.subheader("Registro dei processi")
    history_jobs=jobs()
    if not history_jobs.empty:
        st.dataframe(history_jobs[["id","action","status","started_at","finished_at","exit_code","error"]],
                     hide_index=True,use_container_width=True)
        ids=history_jobs.id.astype(int).tolist()
        selected=st.selectbox("Log da consultare",ids,
                              format_func=lambda x:f"#{x} | {history_jobs.loc[history_jobs.id==x,'action'].iloc[0]}")
        row=history_jobs[history_jobs.id==selected].iloc[0]
        log_path=Path(str(row.log_file))
        if log_path.is_file():
            text=log_path.read_text(encoding="utf-8",errors="replace")
            st.code(text[-26000:] or "Log non ancora disponibile",language="text")
        else:
            st.info("Il processo non ha ancora scritto il log.")
    else:
        st.info("Nessuna esecuzione registrata.")
    if st.button("Aggiorna stati e log",key="refresh"):
        st.rerun()

st.sidebar.markdown(
    '<div class="brand-logo"><span class="brand-mark" aria-hidden="true">✦</span>'
    '<span>WeFix<span class="brand-dot">.it</span></span></div>'
    '<div class="brand-caption">PRICE INTELLIGENCE</div>', unsafe_allow_html=True)
page=st.sidebar.radio("Navigazione",[
    "Panoramica","Prezzi ricondizionati","Valuta usato","Confronto prezzi",
    "Storico scarichi","Esecuzioni"
],label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption("● Archivio locale · accesso da questo dispositivo")

st.title("WeFix · Price Intelligence")
st.markdown('<p class="brand-subtitle">Osservatorio prezzi, valutazioni e raccolte storiche degli iPhone</p>',
            unsafe_allow_html=True)

if page=="Panoramica":
    st.markdown('<div class="hero"><h2>Il mercato dei ricondizionati, in un unico posto.</h2>'
                '<p>Prezzi di vendita, offerte di acquisto e andamento delle quotazioni nel tempo.</p></div>',
                unsafe_allow_html=True)
    snapshots_df=snapshots()
    c1,c2,c3=st.columns(3)
    c1.metric("Totale estrazioni",snapshots_df[["kind","source_id"]].drop_duplicates().shape[0] if not snapshots_df.empty else 0)
    c2.metric("Scarichi ricondizionati",snapshots_df[snapshots_df.kind=="sale"].source_id.nunique() if not snapshots_df.empty else 0)
    c3.metric("Scarichi valutazioni",snapshots_df[snapshots_df.kind=="tradein"].source_id.nunique() if not snapshots_df.empty else 0)
    if not snapshots_df.empty:
        st.subheader("Ultime rilevazioni")
        st.dataframe(snapshots_df[snapshots_df.is_primary==1].head(12)[["kind","scanned_at","filename","record_count"]],
                     hide_index=True,use_container_width=True)
        timeline=snapshots_df[snapshots_df.is_primary==1].copy()
        timeline["mese"]=timeline.scanned_at.astype(str).str.slice(0,7)
        plotted=timeline.groupby(["mese","kind"]).size().unstack(fill_value=0)
        st.subheader("Frequenza delle estrazioni")
        st.bar_chart(plotted)
    else:
        st.info("L'archivio è pronto ma ancora vuoto. Apri Esecuzioni e avvia l'importazione Drive.")
elif page=="Prezzi ricondizionati":
    st.header("Prezzi vendita ricondizionati")
    view_prices("sale")
elif page=="Valuta usato":
    st.header("Valutazioni riconosciute ai privati")
    view_prices("tradein")
elif page=="Confronto prezzi":
    st.header("Confronto vendita vs valutazione")
    comparison()
elif page=="Storico scarichi":
    st.header("Archivio di tutte le estrazioni")
    historical()
else:
    st.header("Esecuzioni e automazioni")
    executions()
