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


def normalizar(texto):
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


print("Lendo CSV...")

df = pd.read_csv(
    "dados_producao.csv",
    sep=";",
    encoding="utf-8",
    engine="python",
    on_bad_lines="skip"
)

df.columns = [normalizar(c) for c in df.columns]

# normalizar os valores principais
df["SEU NOME"] = df["SEU NOME"].astype(str).str.strip()
df["FUNCAO"] = df["FUNCAO"].astype(str).str.strip()
df["MODELO"] = df["MODELO"].astype(str).str.strip()
df["NUMERO DA FICHA"] = (df["NUMERO DA FICHA"].astype(str).str.replace(".", "", regex=False).str.replace(",", "", regex=False).str.strip())
df["NUMERO DA FICHA"] = pd.to_numeric(df["NUMERO DA FICHA"], errors="coerce").astype("Int64")
df["QUANTIDADE DE PAR"] = pd.to_numeric(df["QUANTIDADE DE PAR"], errors="coerce").fillna(0).astype(int)
df["CARIMBO DE DATA/HORA"] = pd.to_datetime(df["CARIMBO DE DATA/HORA"], errors="coerce")

print("Linhas encontradas:", len(df))

db = SessionLocal()

try:
    # -----------------------------
    # 1) LEVANTAR VALORES ÚNICOS
    # -----------------------------
    nomes_operadores = set(df["SEU NOME"].dropna().unique())
    nomes_funcoes = set(df["FUNCAO"].dropna().unique())
    nomes_modelos = set(df["MODELO"].dropna().unique())
    numeros_ficha = set(df["NUMERO DA FICHA"].dropna().unique())

    # -----------------------------
    # 2) BUSCAR EXISTENTES
    # -----------------------------
    operadores_existentes = db.query(UsuarioOperacional).all()
    funcoes_existentes = db.query(Funcao).all()
    formularios_existentes = db.query(Formulario).all()
    fichas_existentes = db.query(Ficha).all()

    operadores_map = {o.nome: o for o in operadores_existentes}
    funcoes_map = {f.nome: f for f in funcoes_existentes}
    formularios_map = {f.nome_modelo: f for f in formularios_existentes}
    fichas_map = {str(f.numero_ficha): f for f in fichas_existentes}

    # -----------------------------
    # 3) CRIAR OPERADORES FALTANTES
    # -----------------------------
    novos_operadores = []
    for nome in nomes_operadores:
        if nome not in operadores_map:
            novo = UsuarioOperacional(
                nome=nome,
                senha="1234",
                tipo="IMPORTADO"
            )
            novos_operadores.append(novo)

    if novos_operadores:
        db.add_all(novos_operadores)
        db.flush()
        for o in novos_operadores:
            operadores_map[o.nome] = o
        print(f"{len(novos_operadores)} operadores criados")

    # -----------------------------
    # 4) CRIAR FUNÇÕES FALTANTES
    # -----------------------------
    novas_funcoes = []
    for nome in nomes_funcoes:
        if nome not in funcoes_map:
            nova = Funcao(nome=nome)
            novas_funcoes.append(nova)

    if novas_funcoes:
        db.add_all(novas_funcoes)
        db.flush()
        for f in novas_funcoes:
            funcoes_map[f.nome] = f
        print(f"{len(novas_funcoes)} funções criadas")

    # -----------------------------
    # 5) CRIAR MODELOS FALTANTES
    # -----------------------------
    novos_formularios = []
    for nome in nomes_modelos:
        if nome not in formularios_map:
            novo = Formulario(
                nome_modelo=nome,
                ativo=True
            )
            novos_formularios.append(novo)

    if novos_formularios:
        db.add_all(novos_formularios)
        db.flush()
        for f in novos_formularios:
            formularios_map[f.nome_modelo] = f
        print(f"{len(novos_formularios)} modelos criados")

    # -----------------------------
    # 6) CRIAR FICHAS FALTANTES
    # usa a primeira ocorrência de cada ficha
    # -----------------------------
    novas_fichas = []
    fichas_df = df.drop_duplicates(subset=["NUMERO DA FICHA"])

    for _, row in fichas_df.iterrows():
        numero_ficha = str(row["NUMERO DA FICHA"]).strip()
        modelo = row["MODELO"]
        quantidade = int(row["QUANTIDADE DE PAR"])

        if numero_ficha not in fichas_map:
            formulario = formularios_map.get(modelo)
            if not formulario:
                continue

            ficha = Ficha(
                numero_ficha=numero_ficha,
                token_qr=str(uuid.uuid4()),
                quantidade_total=quantidade,
                formulario_id=formulario.id
            )
            novas_fichas.append(ficha)

    if novas_fichas:
        db.add_all(novas_fichas)
        db.flush()
        for f in novas_fichas:
            fichas_map[str(f.numero_ficha)] = f
        print(f"{len(novas_fichas)} fichas criadas")

    # -----------------------------
    # 7) CRIAR PRODUÇÕES EM LOTE
    # -----------------------------
    producoes = []

    for _, row in df.iterrows():
        nome = row["SEU NOME"]
        nome_funcao = row["FUNCAO"]
        modelo = row["MODELO"]
        numero_ficha = str(row["NUMERO DA FICHA"]).strip()
        quantidade = int(row["QUANTIDADE DE PAR"])
        data = row["CARIMBO DE DATA/HORA"]

        operador = operadores_map.get(nome)
        funcao = funcoes_map.get(nome_funcao)
        ficha = fichas_map.get(numero_ficha)

        if not operador or not funcao or not ficha:
            continue

        if pd.isna(data):
            data = datetime.utcnow()
        else:
            data = data.to_pydatetime()

        producoes.append(
            Producao(
                ficha_id=ficha.id,
                funcao_id=funcao.id,
                usuario_id=operador.id,
                quantidade=quantidade,
                criado_em=data
            )
        )

    print("Produções para inserir:", len(producoes))

    lote = 1000
    for i in range(0, len(producoes), lote):
        db.add_all(producoes[i:i+lote])
        db.commit()
        print(f"{min(i+lote, len(producoes))} registros importados...")

    print("\nImportação finalizada")
    print("Registros importados:", len(producoes))

except Exception as e:
    db.rollback()
    print("Erro geral:", e)

finally:
    db.close()
