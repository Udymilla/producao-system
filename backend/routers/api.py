from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List

from backend.database import get_db
from backend.models import Producao, Ficha
from backend.schemas import ProducaoResponse, FichaResponse
from backend.security import login_required

router = APIRouter(prefix="/api")

# ======================================================
# PRODUÇÕES (LISTAGEM COM FILTRO)
# ======================================================

@router.get("/producoes", response_model=List[ProducaoResponse])
@login_required
def listar_producoes(
    request: Request,
    data_inicial: str | None = Query(
        None, description="Data inicial no formato DD-MM-YYYY"
    ),
    data_final: str | None = Query(
        None, description="Data final no formato DD-MM-YYYY"
    ),
    db: Session = Depends(get_db)
):
    query = db.query(Producao)

    if data_inicial:
        try:
            inicio = datetime.strptime(data_inicial, "%d-%m-%Y")
            query = query.filter(Producao.criado_em >= inicio)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Data inicial inválida. Use DD-MM-YYYY."
            )

    if data_final:
        try:
            fim = datetime.strptime(data_final, "%d-%m-%Y")
            query = query.filter(Producao.criado_em <= fim)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Data final inválida. Use DD-MM-YYYY."
            )

    producoes = query.order_by(Producao.criado_em.desc()).all()

    return [
        {
            "id": p.id,
            "operador": p.operador,
            "produto": getattr(p, "produto", None),
            "quantidade": p.quantidade,
            "valor": p.valor,
            "criado_em": p.criado_em.strftime("%d-%m-%Y %H:%M:%S")
        }
        for p in producoes
    ]


# ======================================================
# RESUMO POR OPERADOR
# ======================================================

@router.get("/resumo")
@login_required
def resumo_por_operador(
    request: Request,
    operador: str | None = Query(None, description="Filtra por nome do operador"),
    data_inicial: str | None = Query(None, description="DD-MM-YYYY"),
    data_final: str | None = Query(None, description="DD-MM-YYYY"),
    db: Session = Depends(get_db)
):
    query = db.query(
        Producao.operador,
        func.sum(Producao.quantidade).label("total_pecas"),
        func.sum(Producao.valor * Producao.quantidade).label("total_valor")
    )

    if operador:
        query = query.filter(Producao.operador.ilike(f"%{operador}%"))

    if data_inicial:
        try:
            inicio = datetime.strptime(data_inicial, "%d-%m-%Y")
            query = query.filter(Producao.criado_em >= inicio)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Data inicial inválida. Use DD-MM-YYYY."
            )

    if data_final:
        try:
            fim = datetime.strptime(data_final, "%d-%m-%Y")
            query = query.filter(Producao.criado_em <= fim)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Data final inválida. Use DD-MM-YYYY."
            )

    resultado = query.group_by(Producao.operador).all()

    return [
        {
            "operador": r.operador,
            "total_pecas": r.total_pecas,
            "total_valor": round(r.total_valor or 0, 2)
        }
        for r in resultado
    ]


# ======================================================
# FICHAS (API)
# ======================================================

@router.get("/fichas", response_model=List[FichaResponse])
@login_required
def listar_fichas(
    request: Request,
    db: Session = Depends(get_db)
):
    return db.query(Ficha).order_by(Ficha.id.desc()).all()
