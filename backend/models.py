from datetime import datetime
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

# ✅ Garante que o Base é o mesmo em todo o projeto
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
    nome = Column(String, nullable=False)
    senha = Column(String, nullable=False)
    funcao = Column(String, nullable=False)
    ativo = Column(Integer, default=1)
    tipo = Column(String, default="operador")

    # ✅ SOMENTE ISSO
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
    url_imagem = Column(String, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # 🔗 RELACIONAMENTOS
    fichas = relationship("Ficha", back_populates="formulario")
    valores = relationship("ValorModelo", back_populates="modelo_ref")


# ==========================================================
# 🔹 FICHAS
# ==========================================================
class Ficha(Base):
    __tablename__ = "fichas"

    id = Column(Integer, primary_key=True, index=True)
    numero_ficha = Column(String, unique=True, index=True)

    formulario_id = Column(Integer, ForeignKey("formularios.id"), nullable=False)
    formulario = relationship("Formulario")

    funcao = Column(String, nullable=False)
    quantidade_total = Column(Integer, nullable=False)
    setor_atual = Column(String)
    status = Column(Enum(StatusFicha), default=StatusFicha.EM_PRODUCAO)
    token_qr = Column(String(64), unique=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # ✅ RELAÇÃO CORRETA
    producoes = relationship("Producao", back_populates="ficha")

# ==========================================================
# 🔹 PRODUÇÃO (Lançamentos feitos pelo sistema ou QR)
# ==========================================================
class Producao(Base):
    __tablename__ = "producao"

    id = Column(Integer, primary_key=True, index=True)

    ficha_id = Column(Integer, ForeignKey("fichas.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios_operacionais.id"), nullable=False)

    quantidade = Column(Integer)
    valor = Column(Float)
    criado_em = Column(DateTime, default=datetime.utcnow)

    ficha = relationship("Ficha", back_populates="producoes")
    usuario = relationship("UsuarioOperacional", back_populates="producoes")

# ==========================================================
# 🔹 USUÁRIOS DO SISTEMA DE LOGIN (geral)
# ==========================================================
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    senha = Column(String, nullable=False)
    perfil = Column(String, nullable=False)  # Ex: 'admin', 'operador'


# ==========================================================
# 🔹 VALORES POR MODELO
# ==========================================================
class ValorModelo(Base):
    __tablename__ = "valores_modelos"

    id = Column(Integer, primary_key=True, index=True)
    modelo_id = Column(Integer, ForeignKey("formularios.id"), nullable=False)

    funcao = Column(String, nullable=False)
    valor_unitario = Column(Float, nullable=False)
    tamanho = Column(String, nullable=True)

    url_imagem = Column(String, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("modelo_id", "funcao", "tamanho", name="uq_modelo_funcao_tamanho"),
    )

    # 🔗 relacionamento com Formulario
    modelo_ref = relationship("Formulario", back_populates="valores")
