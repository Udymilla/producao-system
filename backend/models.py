from datetime import datetime
import enum
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
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

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)

# ==========================================================
# 🔹 FORMULÁRIOS / MODELOS
# ==========================================================
class Funcao(Base):
    __tablename__ = "funcoes"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False, unique=True)

    valores = relationship(
        "ValorModelo",
        back_populates="funcao",
        cascade="all, delete-orphan"
    )
# ==========================================================
# 🔹 FICHAS
# ==========================================================
class Ficha(Base):
    __tablename__ = "fichas"

    id = Column(Integer, primary_key=True)
    formulario_id = Column(
        Integer,
        ForeignKey("formularios.id"),
        nullable=False
    )

    formulario = relationship(
        "Formulario",
        back_populates="fichas"
    )

# ==========================================================
# 🔹 PRODUÇÃO (Lançamentos feitos pelo sistema ou QR)
# ==========================================================
class Producao(Base):
    __tablename__ = "producoes"

    id = Column(Integer, primary_key=True)
    ficha_id = Column(Integer, ForeignKey("fichas.id"))
    operador = Column(String, nullable=False)
    funcao = Column(String, nullable=False)
    quantidade = Column(Integer, nullable=False)
    valor = Column(Float, default=0)
    criado_em = Column(DateTime, default=datetime.utcnow)

    ficha = relationship("Ficha", back_populates="producoes")


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
    __tablename__ = "valores_modelo"

    id = Column(Integer, primary_key=True)

    modelo_id = Column(
        Integer,
        ForeignKey("formularios.id", ondelete="CASCADE"),
        nullable=False
    )

    funcao_id = Column(
        Integer,
        ForeignKey("funcoes.id", ondelete="CASCADE"),
        nullable=False
    )

    valor = Column(Numeric(10, 2), nullable=True)
    tamanho = Column(String, nullable=True)

    modelo = relationship("Formulario", back_populates="valores")
    funcao = relationship("Funcao", back_populates="valores")


class Formulario(Base):
    __tablename__ = "formularios"

    id = Column(Integer, primary_key=True)
    nome_modelo = Column(String, nullable=False)

    valores = relationship(
        "ValorModelo",
        back_populates="modelo",
        cascade="all, delete-orphan"
    )

