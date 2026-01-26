from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# ======================================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ======================================================

# 🔹 AJUSTE SE NECESSÁRIO:
# Exemplo PostgreSQL:
# postgresql://usuario:senha@localhost:5432/nome_do_banco
DATABASE_URL = "postgresql+psycopg://postgres:producao@localhost:5432/producao"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()
# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ======================================================
# DEPENDÊNCIA DE BANCO (USADA NOS ROUTERS)
# ======================================================

def get_db():
    """
    Cria uma sessão de banco por request e fecha automaticamente.
    Usar sempre com:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

