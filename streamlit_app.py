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
    if termo:
        t = termo.lower()
        vis = vis[vis["modelo_produzido"].astype(str).str.lower().str.contains(t, na=False) | vis["tear"].astype(str).str.contains(t, na=False)]
    if produto != "Todos": vis = vis[vis["produto"] == produto]
    if gauge != "Todos": vis = vis[vis["gauge"] == float(gauge)]
    if materia != "Todas": vis = vis[vis["materia_prima"] == materia]
    st.dataframe(vis, use_container_width=True, hide_index=True)
    st.download_button("Baixar base filtrada em CSV", vis.to_csv(index=False).encode("utf-8-sig"), file_name="base_agulhas_filtrada.csv", mime="text/csv")

with tab_importar:
    st.subheader("Importar arquivo atualizado")
    st.warning("A importação substitui todos os registros atuais. Faça um backup antes.")
    arquivo = st.file_uploader("Selecione CSV ou Excel (.xlsx)", type=["csv","xlsx"], key="arquivo_base")
    if arquivo is not None:
        try:
            novo = pd.read_csv(arquivo, dtype={"modelo_produzido": str}, sep=None, engine="python") if arquivo.name.lower().endswith(".csv") else pd.read_excel(arquivo, dtype={"modelo_produzido": str})
            st.write("Pré-visualização do arquivo:")
            st.dataframe(novo.head(10), use_container_width=True, hide_index=True)
            st.caption(f"{len(novo)} linhas detectadas.")
            confirmar = st.checkbox("Confirmo que este arquivo contém a base completa e quero substituir os registros atuais.")
            if st.button("Atualizar banco de dados", type="primary", disabled=not confirmar, key="btn_importar"):
                substituir(novo)
                st.success(f"Base atualizada com {len(novo)} registros.")
                st.rerun()
        except Exception as e:
            st.error(f"Não foi possível ler/validar o arquivo: {e}")
    st.download_button("Baixar cópia completa atual (CSV)", df.to_csv(index=False).encode("utf-8-sig"), file_name="backup_base_agulhas.csv", mime="text/csv")

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
        novo_registro = pd.DataFrame([{"tear":tear,"gauge":gauge_n,"modelo_produzido":modelo,"produto":prod,"materia_prima":mp,"cor":cor,"ponto":ponto,"estrutura":estrutura,"separacao":separacao,"elastano":elastano,"largura":largura,"altura":altura,"agulhas_cm":ag_cm}])
        try:
            novo_registro = normalizar(novo_registro)
            with conectar() as con: novo_registro.to_sql("registros", con, if_exists="append", index=False)
            st.success("Registro salvo.")
            st.rerun()
        except Exception as e: st.error(str(e))

with tab_prever:
    st.subheader("Previsão de agulhas por centímetro")
    st.write("Informe as características para estimar agulhas/cm usando regressão linear treinada com os registros disponíveis.")
    st.info("Esta função prevê somente agulhas por centímetro. Não existe previsão da quantidade total de agulhas por tecimento.")
    if len(df) < 5:
        st.warning("Há menos de 5 registros na base. Importe ou cadastre mais dados reais para testar a regressão.")
    else:
        treino = df[FEATURES + [ALVO]].dropna(subset=FEATURES + [ALVO]).copy()
        if len(treino) < 5 or treino[ALVO].nunique() < 2:
            st.warning("Não há dados válidos suficientes ou variação no valor de agulhas/cm para treinar a regressão.")
        else:
            preprocessador = ColumnTransformer([
                ("numericas", "passthrough", FEATURES_NUMERICAS),
                ("categoricas", OneHotEncoder(handle_unknown="ignore"), FEATURES_CATEGORICAS)
            ])
            modelo_regressao = Pipeline([("preprocessamento", preprocessador), ("regressao", LinearRegression())])
            modelo_regressao.fit(treino[FEATURES], treino[ALVO])
            st.caption(f"Modelo treinado com {len(treino)} registros válidos. É retreinado com a base atual em cada execução.")
            with st.form("form_previsao_agulhas_cm"):
                st.markdown("#### Características do tecimento")
                c1,c2,c3,c4 = st.columns(4)
                p_tear = c1.number_input("Número do tear", min_value=0, step=1, key="p_tear")
                p_gauge = c2.number_input("Gauge", min_value=0, step=1, key="p_gauge")
                p_largura = c3.number_input("Largura (cm)", min_value=0.0, step=0.5, key="p_largura")
                p_altura = c4.number_input("Altura (cm)", min_value=0.0, step=0.5, key="p_altura")
                c5,c6,c7,c8 = st.columns(4)
                p_produto = c5.selectbox("Produto", opcoes_coluna(treino,"produto"), key="p_produto")
                p_materia = c6.selectbox("Matéria-prima", opcoes_coluna(treino,"materia_prima"), key="p_materia")
                p_cor = c7.selectbox("Cor", opcoes_coluna(treino,"cor"), key="p_cor")
                p_ponto = c8.selectbox("Ponto", opcoes_coluna(treino,"ponto"), key="p_ponto")
                c9,c10,c11 = st.columns(3)
                p_estrutura = c9.selectbox("Estrutura", opcoes_coluna(treino,"estrutura"), key="p_estrutura")
                p_separacao = c10.selectbox("Separação", opcoes_coluna(treino,"separacao"), key="p_separacao")
                p_elastano = c11.selectbox("Elastano/elástico", opcoes_coluna(treino,"elastano"), key="p_elastano")
                calcular = st.form_submit_button("Estimar agulhas por centímetro", type="primary")
            if calcular:
                entrada = pd.DataFrame([{"tear":p_tear,"gauge":p_gauge,"largura":p_largura,"altura":p_altura,"produto":p_produto,"materia_prima":p_materia,"cor":p_cor,"ponto":p_ponto,"estrutura":p_estrutura,"separacao":p_separacao,"elastano":p_elastano}])[FEATURES]
                previsao = float(modelo_regressao.predict(entrada)[0])
                st.metric("Estimativa de agulhas por centímetro", f"{previsao:.2f} agulhas/cm")
