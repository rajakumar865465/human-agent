from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="TaskFlow Lite Demo")


def render_template(name: str, **values) -> str:
    content = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(render_template("index.html"))


@app.get("/login", response_class=HTMLResponse)
def login_page(email: str = "", password: str = ""):
    if email and password:
        return HTMLResponse(render_template("dashboard.html", username=email, status="Logged in successfully"))
    return HTMLResponse(render_template("login.html"))


@app.post("/login")
async def login_post(request: Request):
    body = await request.body()
    if body:
        return JSONResponse({"status": "ok", "message": "Login submitted", "length": len(body)})
    return JSONResponse({"status": "ok", "message": "Login endpoint reached"})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(status: str = "Ready"):
    return HTMLResponse(render_template("dashboard.html", username="Demo User", status=status))


@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    return HTMLResponse(render_template("settings.html"))


@app.get("/health")
def health():
    return {"status": "ok", "service": "taskflow-lite"}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


@app.post("/api/login")
def api_login(payload: dict | None = None):
    return {"status": "ok", "token": "demo-token", "payload": payload or {}}


@app.post("/api/signup")
def api_signup(payload: dict | None = None):
    return {"status": "created", "user": payload or {}}


@app.get("/api/me")
def api_me():
    return {"id": 1, "name": "Demo User", "email": "demo@example.com"}


@app.put("/api/settings")
def api_settings(payload: dict | None = None):
    return {"status": "saved", "settings": payload or {}}
