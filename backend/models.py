from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.database import Base

# ==========================================================
# 🔹 ENUMS e STATUS
# ==========================================================
class StatusFicha(str, enum.Enum):
    EM_PRODUCAO = "em_producao"
    EM_ESTOQUE = "em_estoque"
    FINALIZADA = "finalizada"

# ==========================================================
# 🔹 USUÁRIOS DO SISTEMA (admin / líderes)
# ==========================================================
class UsuarioSistema(Base):
    __tablename__ = "usuarios_sistema"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    usuario = Column(String(50), unique=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    cargo = Column(String(50))
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

# ==========================================================
# 🔹 USUÁRIOS OPERACIONAIS (PIN simplificado para o QR)
# ==========================================================
class UsuarioOperacional(Base):
    __tablename__ = "usuarios_operacionais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    codigo = Column(String(20), unique=True, nullable=False)  # ex: luana.p
    pin = Column(String(10), nullable=False)  # ex: 4321
    funcao_padrao = Column(String(50))
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    producoes = relationship("Producao", back_populates="usuario")

# ==========================================================
# 🔹 FORMULÁRIOS / MODELOS
# ==========================================================
class Formulario(Base):
    __tablename__ = "formularios"

    id = Column(Integer, primary_key=True, index=True)
    nome_modelo = Column(String(120), nullable=False)
    tamanhos = Column(String(100))
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    fichas = relationship("Ficha", back_populates="modelo")

# ==========================================================
# 🔹 FICHAS
# ==========================================================
class Ficha(Base):
    __tablename__ = "fichas"

    id = Column(Integer, primary_key=True, index=True)
    numero_ficha = Column(String, unique=True, index=True)
    modelo_id = Column(Integer, ForeignKey("formularios.id"))
    modelo_nome = Column(String, nullable=False)
    funcao = Column(String, nullable=False)
    quantidade_total = Column(Integer, nullable=False)
    setor_atual = Column(String, nullable=True)
    status = Column(Enum(StatusFicha), default=StatusFicha.EM_PRODUCAO)
    token_qr = Column(String(64), unique=True, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    modelo = relationship("Formulario", back_populates="fichas")
    producoes = relationship("Producao", back_populates="ficha")

# ==========================================================
# 🔹 PRODUÇÃO (Lançamentos feitos pelo sistema ou QR)
# ==========================================================
class Producao(Base):
    __tablename__ = "producao"

    id = Column(Integer, primary_key=True, index=True)
    ficha_id = Column(Integer, ForeignKey("fichas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios_operacionais.id"))
    operador = Column(String)
    modelo = Column(String)
    servico = Column(String)
    tamanho = Column(String)
    quantidade = Column(Integer)
    valor = Column(Float)
    criado_em = Column(DateTime, default=datetime.utcnow)

    ficha = relationship("Ficha", back_populates="producoes")
    usuario = relationship("UsuarioOperacional", back_populates="producoes")

# ==========================================================
# 🔹 USUÁRIOS GENÉRICOS (seus originais, mantidos)
# ==========================================================
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    senha = Column(String, nullable=False)
    perfil = Column(String, nullable=False)  # "producao" ou "lider"

class UsuarioOperacional(Base):
    __tablename__ = "usuarios_operacionais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    senha = Column(String, nullable=False)
    funcao = Column(String, nullable=False)  # costura, acabamento, corte, etc.
    ativo = Column(Integer, default=1)       # 1 = ativo, 0 = inativo
