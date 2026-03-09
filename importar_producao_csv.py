import pandas as pd
import unicodedata
import uuid
from datetime import datetime

from backend.database import SessionLocal
from backend.models import (
    UsuarioOperacional,
    Producao,
    Ficha,
    Formulario,
    Funcao
)


# -----------------------------
# NORMALIZAR TEXTO
# -----------------------------
def normalizar(texto):
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


# -----------------------------
# INICIO
# -----------------------------
print("Lendo CSV...")

df = pd.read_csv(
    "dados_producao.csv",
    sep=";",
    encoding="utf-8",
    engine="python",
    on_bad_lines="skip"
)

# remove espaços das colunas
df.columns = df.columns.str.strip()

# normaliza colunas
df.columns = [normalizar(c) for c in df.columns]

print("Linhas encontradas:", len(df))


# -----------------------------
# BANCO
# -----------------------------
db = SessionLocal()

erros = 0
importados = 0


# -----------------------------
# LOOP IMPORTAÇÃO
# -----------------------------
for i, row in df.iterrows():

    try:

        nome = str(row["SEU NOME"]).strip()
        funcao_nome = str(row["FUNCAO"]).strip()
        modelo = str(row["MODELO"]).strip()

        quantidade = int(row["QUANTIDADE DE PAR"])
        numero_ficha = int(row["NUMERO DA FICHA"])

        data = pd.to_datetime(row["CARIMBO DE DATA/HORA"], errors="coerce")

        if pd.isna(data):
            data = datetime.utcnow()

        # -----------------------------
        # OPERADOR
        # -----------------------------
        operador = db.query(UsuarioOperacional).filter(
            UsuarioOperacional.nome == nome
        ).first()

        if not operador:
            operador = UsuarioOperacional(
                nome=nome,
                senha="1234",
                tipo=funcao_nome
            )
            db.add(operador)
            db.flush()
            print("Operador criado:", nome)

        # -----------------------------
        # FUNÇÃO
        # -----------------------------
        funcao = db.query(Funcao).filter(
            Funcao.nome == funcao_nome
        ).first()

        if not funcao:
            funcao = Funcao(nome=funcao_nome)
            db.add(funcao)
            db.flush()
            print("Função criada:", funcao_nome)

        # -----------------------------
        # FORMULÁRIO / MODELO
        # -----------------------------
        formulario = db.query(Formulario).filter(
            Formulario.nome_modelo == modelo
        ).first()

        if not formulario:
            formulario = Formulario(
                nome_modelo=modelo,
                ativo=True
            )
            db.add(formulario)
            db.flush()
            print("Modelo criado:", modelo)

        # -----------------------------
        # FICHA
        # -----------------------------
        ficha = db.query(Ficha).filter(
            Ficha.numero_ficha == numero_ficha
        ).first()

        if not ficha:
            ficha = Ficha(
                numero_ficha=numero_ficha,
                token_qr=str(uuid.uuid4()),
                quantidade_total=quantidade,
                formulario_id=formulario.id
            )

            db.add(ficha)
            db.flush()
            print("Ficha criada:", numero_ficha)

        # -----------------------------
        # PRODUÇÃO
        # -----------------------------
        producao = Producao(
            ficha_id=ficha.id,
            funcao_id=funcao.id,
            usuario_id=operador.id,
            quantidade=quantidade,
            criado_em=data
        )

        db.add(producao)

        importados += 1

        # commit em lote
        if importados % 500 == 0:
            db.commit()
            print(importados, "registros importados...")

    except Exception as e:
        db.rollback()

        erros += 1
        print("Erro linha", i, ":", e)


# -----------------------------
# FINAL
# -----------------------------
db.commit()

print("\nImportação finalizada")
print("Registros importados:", importados)
print("Erros:", erros)