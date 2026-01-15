from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_senha(senha: str):
    return pwd_context.hash(senha)

def verificar_senha(senha: str, senha_hash: str):
    return pwd_context.verify(senha, senha_hash)
    
# Ambiente único de templates para todo o sistema
templates = Jinja2Templates(directory="backend/frontend/templates")

# Disponibiliza now() globalmente no Jinja
templates.env.globals["now"] = datetime.now

