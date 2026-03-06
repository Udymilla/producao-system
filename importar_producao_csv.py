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
    Funcao,
)


def normalizar(texto):
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


def parse_data(valor):
    if pd.isna(valor):
        return datetime.now()

    try:
        return pd.to_datetime(valor).to_pydatetime()
    except Exception:
        return datetime.now()


print("Lendo CSV...")

df = pd.read_csv(
    "dados_producao.csv",
    sep=";",
    encoding="utf-8",
    engine="python",
    on_bad_lines="skip"
)

df.columns = df.columns.str.strip()
df.columns = [normalizar(c) for c in df.columns]

print("Linhas encontradas:", len(df))

db = SessionLocal()

erros = 0
importados = 0

for i, row in df.iterrows():
    try:
        nome = str(row["SEU NOME"]).strip()
        nome_funcao = str(row["FUNCAO"]).strip()
        modelo = str(row["MODELO"]).strip()
        quantidade = int(row["QUANTIDADE DE PAR"])
        numero_ficha = int(row["NUMERO DA FICHA"])
        data = parse_data(row["CARIMBO DE DATA/HORA"])

        # 1) OPERADOR
        operador = db.query(UsuarioOperacional).filter(
            UsuarioOperacional.nome == nome
        ).first()

        if not operador:
            operador = UsuarioOperacional(
                nome=nome,
                senha="1234",
                tipo=nome_funcao
            )
            db.add(operador)
            db.commit()
            db.refresh(operador)
            print("Operador criado:", nome)

        # 2) FUNÇÃO
        funcao = db.query(Funcao).filter(
            Funcao.nome == nome_funcao
        ).first()

        if not funcao:
            funcao = Funcao(nome=nome_funcao)
            db.add(funcao)
            db.commit()
            db.refresh(funcao)
            print("Função criada:", nome_funcao)

        # 3) MODELO / FORMULÁRIO
        formulario = db.query(Formulario).filter(
            Formulario.nome_modelo == modelo
        ).first()

        if not formulario:
            formulario = Formulario(
                nome_modelo=modelo,
                ativo=True
            )
            db.add(formulario)
            db.commit()
            db.refresh(formulario)
            print("Modelo criado:", modelo)

        # 4) FICHA
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
            db.commit()
            db.refresh(ficha)
            print("Ficha criada:", numero_ficha)

        # 5) PRODUÇÃO
        producao = Producao(
            ficha_id=ficha.id,
            funcao_id=funcao.id,
            usuario_id=operador.id,
            quantidade=quantidade,
            criado_em=data
        )

        db.add(producao)
        importados += 1

        if importados % 500 == 0:
            db.commit()
            print(f"{importados} registros importados...")

    except Exception as e:
        erros += 1
        print("Erro na linha", i, ":", e)

db.commit()

print("\nImportação finalizada")
print("Registros importados:", importados)
print("Erros:", erros)