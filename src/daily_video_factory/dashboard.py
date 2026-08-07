from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import __version__
from .config import Settings
from .state import RunStore


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="AtlasForge AI", version=__version__)
    store = RunStore(settings.output_directory.resolve())

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, object]]:
        return store.list_runs()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AtlasForge AI</title><style>
:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif;background:#0d1117;color:#e6edf3}
body{max-width:1120px;margin:0 auto;padding:52px 24px}header{display:flex;justify-content:space-between;align-items:end}
h1{font-size:44px;margin:0;letter-spacing:-1.5px}.muted{color:#8b949e}.pill{padding:5px 10px;border:1px solid #30363d;border-radius:999px}
.grid{display:grid;gap:14px;margin-top:34px}.run{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:20px;display:grid;grid-template-columns:1.6fr .8fr .8fr;gap:16px}
.status{font-weight:700;color:#f2cc60}.published{color:#56d364}.failed{color:#ff7b72}.ready{color:#79c0ff}
@media(max-width:700px){.run{grid-template-columns:1fr}h1{font-size:34px}}
</style></head><body><header><div><div class="muted">AUTONOMOUS VIDEO OPERATIONS</div><h1>AtlasForge AI</h1></div><div class="pill" id="updated">loading</div></header>
<main class="grid" id="runs"></main><script>
const escapeHtml=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
async function refresh(){const data=await fetch('/api/runs').then(r=>r.json());document.querySelector('#runs').innerHTML=data.map(r=>`<article class="run"><div><div class="muted">${escapeHtml(r.publication_date)}</div><strong>${escapeHtml(r.topic||'Topic pending')}</strong></div><div><div class="muted">STAGE</div>${escapeHtml(r.current_stage)}</div><div><div class="muted">STATUS</div><span class="status ${escapeHtml(r.status)}">${escapeHtml(r.status)}</span></div></article>`).join('')||'<p class="muted">No runs yet.</p>';document.querySelector('#updated').textContent=new Date().toLocaleTimeString()}
refresh();setInterval(refresh,5000);
</script></body></html>"""

    return app
