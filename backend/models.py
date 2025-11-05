from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum, Text, UniqueConstraint
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
    _tablename_ = "usuarios_sistema"

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
    _tablename_ = "usuarios_operacionais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    senha = Column(String, nullable=False)
    funcao = Column(String, nullable=False)  # costura, acabamento, corte, etc.
    ativo = Column(Integer, default=1)  # 1 = ativo, 0 = inativo

    # 🔗 Relacionamentos
    fichas = relationship("Ficha", back_populates="usuario")
    producoes = relationship("Producao", back_populates="usuario")


# ==========================================================
# 🔹 FORMULÁRIOS / MODELOS
# ==========================================================
class Formulario(Base):
    _tablename_ = "formularios"

    id = Column(Integer, primary_key=True, index=True)
    nome_modelo = Column(String(120), nullable=False)
    tamanhos = Column(String(100))
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


# ==========================================================
# 🔹 FICHAS
# ==========================================================
class Ficha(Base):
    _tablename_ = "fichas"

    id = Column(Integer, primary_key=True, index=True)
    numero_ficha = Column(String, unique=True, index=True)
    modelo = Column(String, nullable=False)  # Ex: CAMISA OPERACIONAL
    funcao = Column(String, nullable=False)
    quantidade_total = Column(Integer, nullable=False)
    setor_atual = Column(String, nullable=True)
    status = Column(Enum(StatusFicha), default=StatusFicha.EM_PRODUCAO)
    token_qr = Column(String(64), unique=True, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # 🔗 RELACIONAMENTO COM USUÁRIO OPERACIONAL
    usuario_id = Column(Integer, ForeignKey("usuarios_operacionais.id"))
    usuario = relationship("UsuarioOperacional", back_populates="fichas")

    # 🔗 RELACIONAMENTO COM PRODUÇÃO
    producoes = relationship("Producao", back_populates="ficha")


# ==========================================================
# 🔹 PRODUÇÃO (Lançamentos feitos pelo sistema ou QR)
# ==========================================================
class Producao(Base):
    _tablename_ = "producao"

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

    # 🔗 RELACIONAMENTOS
    ficha = relationship("Ficha", back_populates="producoes")
    usuario = relationship("UsuarioOperacional", back_populates="producoes")


# ==========================================================
# 🔹 USUÁRIOS DO SISTEMA DE LOGIN (acesso geral)
# ==========================================================
class Usuario(Base):
    _tablename_ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    senha = Column(String, nullable=False)
    perfil = Column(String, nullable=False)  # Ex: administrador, líder, produção


# ==========================================================
# 🔹 VALORES POR MODELO
# ==========================================================
class ValorModelo(Base):
    _tablename_ = "valores_modelos"

    id = Column(Integer, primary_key=True, index=True)
    modelo = Column(String, nullable=False)
    funcao = Column(String)
    valor_unitario = Column(Float, nullable=False)
    tamanho = Column(String, nullable=True)
    url_imagem = Column(String, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    _table_args_ = (
        UniqueConstraint("modelo", "funcao", name="uq_modelo_funcao"),
    )