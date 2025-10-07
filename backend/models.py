from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from database import Base

class Producao(Base):
    __tablename__ = "producao"

    id = Column(Integer, primary_key=True, index=True)
    ficha_id = Column(String, index=True)
    operador = Column(String)
    modelo = Column(String)
    servico = Column(String)
    tamanho = Column(String)
    quantidade = Column(Integer)
    valor = Column(Float)
    criado_em = Column(DateTime, default=datetime.utcnow)
