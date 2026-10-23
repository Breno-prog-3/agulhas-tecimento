import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "agulhas.db"
CSV_INICIAL = APP_DIR / "base_agulhas_atual.csv"

COLUNAS = ["tear","gauge","modelo_produzido","produto","materia_prima","cor","ponto","estrutura","separacao","elastano","largura","altura","agulhas_cm"]
NUMERICAS = ["tear","gauge","largura","altura","agulhas_cm"]
FEATURES_NUMERICAS = ["tear","gauge","largura","altura"]
FEATURES_CATEGORICAS = ["produto","materia_prima","cor","ponto","estrutura","separacao","elastano"]
FEATURES = FEATURES_NUMERICAS + FEATURES_CATEGORICAS
ALVO = "agulhas_cm"

st.set_page_config(page_title="Cadastro de Tecimento", page_icon="🧶", layout="wide")

def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def normalizar(df):
    df = df.copy()
    aliases = {
        "numero do tear":"tear", "número do tear":"tear", "modelo produzido":"modelo_produzido",
        "materia-prima":"materia_prima", "matéria-prima":"materia_prima",
        "separação":"separacao", "agulhas/cm":"agulhas_cm", "agulhas por cm":"agulhas_cm",
        "elastano/elástico":"elastano", "elastano/elastico":"elastano"
    }
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={c: aliases[c] for c in df.columns if c in aliases})
    faltantes = [c for c in COLUNAS if c not in df.columns]
    if faltantes:
        raise ValueError("Colunas ausentes: " + ", ".join(faltantes))
    df = df[COLUNAS]
    df["modelo_produzido"] = df["modelo_produzido"].fillna("").astype(str).str.strip()
    for c in [x for x in COLUNAS if x not in NUMERICAS]:
        df[c] = df[c].fillna("").astype(str).str.strip().str.upper()
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    if df[NUMERICAS].isna().any().any():
        linhas = (df[df[NUMERICAS].isna().any(axis=1)].index + 2).tolist()
        raise ValueError("Valores numéricos ausentes ou inválidos nas linhas: " + ", ".join(map(str, linhas)))
    return df

def inicializar():
    with conectar() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tear REAL, gauge REAL, modelo_produzido TEXT,
            produto TEXT, materia_prima TEXT, cor TEXT, ponto TEXT, estrutura TEXT,
            separacao TEXT, elastano TEXT, largura REAL, altura REAL, agulhas_cm REAL
        )""")
        n = con.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
        if n == 0 and CSV_INICIAL.exists():
            normalizar(pd.read_csv(CSV_INICIAL, dtype={"modelo_produzido": str})).to_sql("registros", con, if_exists="append", index=False)

def carregar():
    with conectar() as con:
        return pd.read_sql_query("SELECT " + ", ".join(COLUNAS) + " FROM registros ORDER BY id", con)

def substituir(df):
    limpo = normalizar(df)
    with conectar() as con:
        con.execute("DELETE FROM registros")
        limpo.to_sql("registros", con, if_exists="append", index=False)

def opcoes_coluna(df, coluna):
    valores = sorted(v for v in df[coluna].dropna().astype(str).unique().tolist() if v.strip())
    return valores if valores else ["NÃO INFORMADO"]

inicializar()
st.title("🧶 Cadastro de Tecimento de Agulhas")
st.caption("Consulta, manutenção de registros e regressão linear para estimar apenas agulhas por centímetro. Não calcula quantidade total de agulhas por tecimento.")
df = carregar()
m1, m2, m3 = st.columns(3)
m1.metric("Registros", len(df))
m2.metric("Modelos produzidos", df["modelo_produzido"].nunique() if len(df) else 0)
m3.metric("Produtos", df["produto"].nunique() if len(df) else 0)

tab_consulta, tab_importar, tab_adicionar, tab_prever = st.tabs(["🔎 Consultar base","🔄 Atualizar base","➕ Novo registro","📈 Regressão linear"])

with tab_consulta:
    st.subheader("Pesquisar e filtrar")
    f1, f2, f3, f4 = st.columns(4)
    termo = f1.text_input("Buscar por modelo ou tear")
    produtos = opcoes_coluna(df, "produto") if len(df) else []
    produto = f2.selectbox("Produto", ["Todos"] + produtos)
    gauges = sorted(df["gauge"].dropna().unique().tolist()) if len(df) else []
    gauge = f3.selectbox("Gauge", ["Todos"] + [str(int(x)) if float(x).is_integer() else str(x) for x in gauges])
    materias = opcoes_coluna(df, "materia_prima") if len(df) else []
    materia = f4.selectbox("Matéria-prima", ["Todas"] + materias)
    vis = df.copy()
