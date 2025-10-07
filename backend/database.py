from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ⚙️ Substitua '1234' pela sua senha do PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:1234@localhost:5432/producao"

# 🔗 Conexão com o banco
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
    