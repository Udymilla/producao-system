from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import RedirectResponse
from backend.database import engine, Base
from backend.routers import auth, operador, admin, api

# cria tabelas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema de Produção Dadalto")

# middleware de sessão
app.add_middleware(
    SessionMiddleware,
    secret_key="supersegredo123"
)

# arquivos estáticos
app.mount(
    "/static",
    StaticFiles(directory="backend/frontend/static"),
    name="static"
)

# routers
app.include_router(auth.router)
app.include_router(operador.router)
app.include_router(admin.router)
app.include_router(api.router)

@app.get("/")
async def home():
    return RedirectResponse("/login")
