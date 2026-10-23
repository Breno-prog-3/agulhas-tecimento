import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "agulhas.db"
CSV_INICIAL = APP_DIR / "base_agulhas_atual.csv"

COLUNAS = ["tear","gauge","modelo_produzido","produto","materia_prima","cor",
           "ponto","estrutura","separacao","elastano","largura","altura","agulhas_cm"]
NUMERICAS = ["tear","gauge","largura","altura","agulhas_cm"]

st.set_page_config(page_title="Cadastro de Tecimento", page_icon="🧶", layout="wide")

def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def normalizar(df):
    df = df.copy()
    # aceita cabeçalhos com espaços/acentos comuns exportados de planilhas
    aliases = {
        "numero do tear":"tear", "número do tear":"tear", "modelo produzido":"modelo_produzido",
        "materia-prima":"materia_prima", "matéria-prima":"materia_prima",
        "separação":"separacao", "agulhas/cm":"agulhas_cm", "agulhas por cm":"agulhas_cm"
    }
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={c: aliases[c] for c in df.columns if c in aliases})
    faltantes = [c for c in COLUNAS if c not in df.columns]
    if faltantes:
        raise ValueError("Colunas ausentes: " + ", ".join(faltantes))
    df = df[COLUNAS]
    for c in ["modelo_produzido"]:
        df[c] = df[c].astype(str).str.strip()
    for c in [x for x in COLUNAS if x not in NUMERICAS]:
        df[c] = df[c].fillna("").astype(str).str.strip().str.upper()
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    if df[NUMERICAS].isna().any().any():
        bad = df[df[NUMERICAS].isna().any(axis=1)].index.tolist()
        raise ValueError(f"Valores numéricos ausentes ou inválidos nas linhas: {bad}")
    return df

def inicializar():
    with conectar() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tear REAL, gauge REAL, modelo_produzido TEXT, produto TEXT,
            materia_prima TEXT, cor TEXT, ponto TEXT, estrutura TEXT,
            separacao TEXT, elastano TEXT, largura REAL, altura REAL, agulhas_cm REAL
        )""")
        n = con.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
        if n == 0 and CSV_INICIAL.exists():
            inicial = normalizar(pd.read_csv(CSV_INICIAL, dtype={"modelo_produzido": str}))
            inicial.to_sql("registros", con, if_exists="append", index=False)

def carregar():
    with conectar() as con:
        return pd.read_sql_query("SELECT " + ", ".join(COLUNAS) + " FROM registros ORDER BY id", con)

def substituir(df):
    limpo = normalizar(df)
    with conectar() as con:
        con.execute("DELETE FROM registros")
        limpo.to_sql("registros", con, if_exists="append", index=False)

inicializar()
st.title("🧶 Cadastro de Tecimento de Agulhas")
st.caption("Consulta e manutenção dos registros reais. Não há modelo de regressão nem previsão de agulhas.")
df = carregar()
a,b,c = st.columns(3)
a.metric("Registros", len(df))
b.metric("Modelos produzidos", df["modelo_produzido"].nunique() if len(df) else 0)
c.metric("Produtos", df["produto"].nunique() if len(df) else 0)

tab_consulta, tab_importar, tab_adicionar = st.tabs(["🔎 Consultar base", "🔄 Atualizar base", "➕ Novo registro"])
with tab_consulta:
    st.subheader("Pesquisar e filtrar")
    f1,f2,f3,f4 = st.columns(4)
    termo = f1.text_input("Buscar por modelo ou tear")
    produtos = sorted(df["produto"].dropna().unique().tolist()) if len(df) else []
    produto = f2.selectbox("Produto", ["Todos"]+produtos)
    gauges = sorted(df["gauge"].dropna().unique().tolist()) if len(df) else []
    gauge = f3.selectbox("Gauge", ["Todos"]+[str(int(x)) if float(x).is_integer() else str(x) for x in gauges])
    materias = sorted(df["materia_prima"].dropna().unique().tolist()) if len(df) else []
    materia = f4.selectbox("Matéria-prima", ["Todas"]+materias)
    vis = df.copy()
    if termo:
        vis = vis[vis.apply(lambda r: termo.lower() in str(r["modelo_produzido"]).lower() or termo.lower() in str(r["tear"]), axis=1)]
    if produto != "Todos": vis = vis[vis["produto"] == produto]
    if gauge != "Todos": vis = vis[vis["gauge"] == float(gauge)]
    if materia != "Todas": vis = vis[vis["materia_prima"] == materia]
    st.dataframe(vis, use_container_width=True, hide_index=True)
    st.download_button("Baixar base filtrada em CSV", vis.to_csv(index=False).encode("utf-8-sig"),
                       file_name="base_agulhas_filtrada.csv", mime="text/csv")

with tab_importar:
    st.subheader("Importar arquivo atualizado")
    st.warning("A importação substitui todos os registros atuais. Exporte uma cópia antes se precisar preservar o histórico.")
    arquivo = st.file_uploader("Selecione CSV ou Excel (.xlsx)", type=["csv","xlsx"])
    if arquivo is not None:
        try:
            if arquivo.name.lower().endswith(".csv"):
                novo = pd.read_csv(arquivo, dtype={"modelo_produzido": str})
            else:
                novo = pd.read_excel(arquivo, dtype={"modelo_produzido": str})
            st.write("Pré-visualização do arquivo:")
            st.dataframe(novo.head(10), use_container_width=True, hide_index=True)
            st.caption(f"{len(novo)} linhas detectadas.")
            confirmar = st.checkbox("Confirmo que este arquivo é a nova base completa e quero substituir a base atual.")
            if st.button("Atualizar banco de dados", type="primary", disabled=not confirmar):
                substituir(novo)
                st.success(f"Base atualizada com {len(novo)} registros. Recarregue a página se necessário.")
                st.rerun()
        except Exception as e:
            st.error(f"Não foi possível ler/validar o arquivo: {e}")
    st.download_button("Baixar cópia completa atual (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="backup_base_agulhas.csv", mime="text/csv")

with tab_adicionar:
    st.subheader("Cadastrar registro manualmente")
    with st.form("novo_registro"):
        x1,x2,x3,x4 = st.columns(4)
        tear = x1.number_input("Número do tear", min_value=0, step=1)
        gauge_n = x2.number_input("Gauge", min_value=0, step=1)
        modelo = x3.text_input("Modelo produzido")
        prod = x4.selectbox("Produto", ["GOLA","RIBANA","OUTRO"])
        x5,x6,x7,x8 = st.columns(4)
        mp = x5.text_input("Matéria-prima")
        cor = x6.text_input("Cor")
        ponto = x7.text_input("Ponto")
        estrutura = x8.text_input("Estrutura")
        x9,x10,x11,x12 = st.columns(4)
        separacao = x9.text_input("Separação")
        elastano = x10.text_input("Elastano/elástico (ex.: N)")
        largura = x11.number_input("Largura (cm)", min_value=0.0, step=0.5)
        altura = x12.number_input("Altura (cm)", min_value=0.0, step=0.5)
        ag_cm = st.number_input("Agulhas/cm (valor real registrado)", min_value=0.0, step=0.1)
        salvar = st.form_submit_button("Salvar registro")
    if salvar:
        novo = pd.DataFrame([{
            "tear":tear,"gauge":gauge_n,"modelo_produzido":modelo,"produto":prod,
            "materia_prima":mp,"cor":cor,"ponto":ponto,"estrutura":estrutura,
            "separacao":separacao,"elastano":elastano,"largura":largura,"altura":altura,
            "agulhas_cm":ag_cm
        }])
        try:
            novo = normalizar(novo)
            with conectar() as con: novo.to_sql("registros", con, if_exists="append", index=False)
            st.success("Registro salvo.")
            st.rerun()
        except Exception as e: st.error(str(e))

st.divider()
st.caption("A base inicial foi transcrita do PDF enviado. Confirme os dados com a fonte original antes de usar em produção.")
