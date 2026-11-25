import gspread
import pandas as pd
import streamlit as st
from datetime import date

st.set_page_config(page_title="Finanças", layout="centered")

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1100px;}
h1 {font-weight: 800; letter-spacing: -0.02em;}
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #181b22, #1f2330);
    border: 1px solid #2a2f3c;
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
div[data-testid="stMetricValue"] {font-size: 1.9rem; font-weight: 700;}
div[data-testid="stMetricLabel"] p {color: #9aa3b2; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em;}
[data-testid="stSidebar"] {background: #12141a;}
.stTabs [data-baseweb="tab-list"] {gap: 8px;}
.stTabs [data-baseweb="tab"] {border-radius: 999px; padding: 6px 16px; background: #181b22;}
.stTabs [aria-selected="true"] {background: #22c55e22; color: #22c55e !important;}
div[data-testid="stDataFrame"] {border-radius: 14px; overflow: hidden; border: 1px solid #2a2f3c;}
div[data-testid="stForm"] {background: #181b22; border: 1px solid #2a2f3c; border-radius: 16px; padding: 20px;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def planilha():
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    return gc.open_by_key(st.secrets["sheet_id"])

@st.cache_data(ttl=30)
def carregar(aba):
    valores = planilha().worksheet(aba).get_all_values()
    if not valores:
        return pd.DataFrame()
    tabela = pd.DataFrame(valores[1:], columns=valores[0])
    if "valor" in tabela.columns:
        tabela["valor"] = pd.to_numeric(
            tabela["valor"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
            errors="coerce",
        ).fillna(0)
    return tabela

def adicionar(aba, linha):
    planilha().worksheet(aba).append_row(linha, value_input_option="USER_ENTERED")
    carregar.clear()

def brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parsear_data(valor):
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        return None
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        convertido = pd.to_datetime(texto, dayfirst=True, errors="coerce")
        if pd.isna(convertido):
            return None
        return convertido.date()

def parsear_booleano(valor):
    return str(valor).strip().upper() in {"TRUE", "VERDADEIRO", "1", "SIM"}

def preparar_lancamentos(tabela):
    resultado = tabela.copy()
    resultado["linha_planilha"] = range(2, len(resultado) + 2)
    if "vencimento" not in resultado.columns:
        resultado["vencimento"] = ""
    if "pago" not in resultado.columns:
        resultado["pago"] = ""
    venc_texto = resultado["vencimento"].astype(str).str.strip()
    data_texto = resultado["data"].astype(str).str.strip() if "data" in resultado.columns else ""
    resultado["vencimento_efetivo"] = venc_texto.where(venc_texto != "", data_texto)
    resultado["vencimento_data"] = resultado["vencimento_efetivo"].apply(parsear_data)
    resultado["pago_status"] = resultado["pago"].apply(parsear_booleano)
    return resultado

mes = st.sidebar.text_input("Mês (AAAA-MM)", value=date.today().strftime("%Y-%m"))

rec = carregar("recorrentes")
lan = preparar_lancamentos(carregar("lancamentos"))
lan_mes = lan[lan["mes"] == mes] if not lan.empty and "mes" in lan.columns else lan

entradas = rec.loc[rec["tipo"] == "entrada", "valor"].sum() + lan_mes.loc[lan_mes["tipo"] == "entrada", "valor"].sum()
despesas = rec.loc[rec["tipo"] == "despesa", "valor"].sum() + lan_mes.loc[lan_mes["tipo"] == "despesa", "valor"].sum()
saldo = entradas - despesas

st.title(f"Finanças • {mes}")

c1, c2, c3 = st.columns(3)
c1.metric("Entradas", brl(entradas))
c2.metric("Despesas", brl(despesas))
c3.metric("Saldo", brl(saldo))

resumo, lancar = st.tabs(["Resumo", "Lançar"])

with resumo:
    st.subheader("Recorrentes (todo mês)")
    st.dataframe(rec, hide_index=True, use_container_width=True)
    st.subheader("Lançamentos do mês")
    st.dataframe(lan_mes, hide_index=True, use_container_width=True)

with lancar:
    with st.form("novo", clear_on_submit=True):
        tipo = st.selectbox("Tipo", ["despesa", "entrada"])
        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
        vencimento = st.date_input("Vencimento", value=date.today())
        pago = st.checkbox("Pago", value=False)
        enviar = st.form_submit_button("Salvar")
        if enviar and descricao:
            adicionar(
                "lancamentos",
                [mes, date.today().isoformat(), tipo, descricao, valor, vencimento.isoformat(), bool(pago)],
            )
            st.rerun()