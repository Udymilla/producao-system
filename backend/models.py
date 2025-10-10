from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime
from backend.database import Base

class Producao(Base):
    __tablename__ = "producao"

    id = Column(Integer, primary_key=True, index=True)
    ficha_id = Column(Integer, ForeignKey("fichas.id"), nullable=False)  # 🔹 relação com Ficha
    operador = Column(String)
    modelo = Column(String)
    servico = Column(String)
    tamanho = Column(String)
    quantidade = Column(Integer)
    valor = Column(Float)
    criado_em = Column(DateTime, default=datetime.utcnow)

from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime
import enum
from backend.database import Base

# 🔹 Status possíveis da ficha
class StatusFicha(str, enum.Enum):
    EM_PRODUCAO = "em_producao"
    EM_ESTOQUE = "em_estoque"
    FINALIZADA = "finalizada"

# 🔹 Modelo da ficha
class Ficha(Base):
    __tablename__ = "fichas"

    id = Column(Integer, primary_key=True, index=True)
    numero_ficha = Column(String, unique=True, index=True)
    modelo = Column(String, nullable=False)
    funcao = Column(String, nullable=False)
    quantidade_total = Column(Integer, nullable=False)
    setor_atual = Column(String, nullable=True)
    status = Column(Enum(StatusFicha), default=StatusFicha.EM_PRODUCAO)
    criado_em = Column(DateTime, default=datetime.utcnow)

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    senha = Column(String, nullable=False)
    perfil = Column(String, nullable=False)  # "producao" ou "lider"