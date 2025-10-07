from fastapi import FastAPI
from database import engine, Base
from models import Producao

app = FastAPI(title="Sistema de Produção Dadalto")

# Cria a tabela no banco, se ainda não existir
Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"mensagem": "🚀 API conectada ao banco 'producao' com sucesso!"}

