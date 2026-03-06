import pandas as pd
import unicodedata
import uuid

from backend.database import SessionLocal
from backend.models import UsuarioOperacional, Producao, Ficha, Formulario


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

# normaliza nomes das colunas
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
        funcao = str(row["FUNCAO"]).strip()
        modelo = str(row["MODELO"]).strip()

        quantidade = int(row["QUANTIDADE DE PAR"])
        numero_ficha = int(row["NUMERO DA FICHA"])

        data = row["CARIMBO DE DATA/HORA"]

        # -----------------------------
        # BUSCAR OU CRIAR OPERADOR
        # -----------------------------
        operador = db.query(UsuarioOperacional).filter(
            UsuarioOperacional.nome == nome
        ).first()

        if not operador:

            operador = UsuarioOperacional(
                nome=nome,
                senha="1234",
                tipo=funcao
            )

            db.add(operador)
            db.commit()
            db.refresh(operador)

            print("Operador criado:", nome)

        # -----------------------------
        # BUSCAR FORMULARIO (MODELO)
        # -----------------------------
        formulario = db.query(Formulario).filter(
            Formulario.nome_modelo == modelo
        ).first()

        if not formulario:
            print("Modelo não encontrado:", modelo)
            erros += 1
            continue

        # -----------------------------
        # BUSCAR OU CRIAR FICHA
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
            db.commit()
            db.refresh(ficha)

        # -----------------------------
        # CRIAR PRODUÇÃO
        # -----------------------------
        producao = Producao(
            ficha_id=ficha.id,
            usuario_id=operador.id,
            quantidade=quantidade,
            criado_em=data
        )

        db.add(producao)

        importados += 1

        # commit em lote (melhor performance)
        if importados % 500 == 0:
            db.commit()
            print(importados, "registros importados...")

    except Exception as e:

        erros += 1
        print("Erro na linha", i, ":", e)


# -----------------------------
# FINAL
# -----------------------------
db.commit()

print("\nImportação finalizada")
print("Registros importados:", importados)
print("Erros:", erros)
