from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ⚙️ ajuste o nome do banco conforme você criou no pgAdmin
DATABASE_URL = "postgresql+psycopg2://postgres:1234@localhost/producao"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
