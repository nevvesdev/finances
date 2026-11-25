import gspread
import pandas as pd
import streamlit as st
from datetime import date

st.set_page_config(page_title="Finanças", layout="centered")

@st.cache_resource
def planilha():
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    return gc.open_by_key(st.secrets["sheet_id"])

@st.cache_data(ttl=30)
def carregar(aba):
    valores = planilha().worksheet(aba).get_all_values()
    df = pd.DataFrame(valores[1:], columns=valores[0])
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(
            df["valor"].str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
            errors="coerce",
        ).fillna(0)
    return df

def adicionar(aba, linha):
    planilha().worksheet(aba).append_row(linha, value_input_option="USER_ENTERED")
    carregar.clear()

def brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

mes = st.sidebar.text_input("Mês (AAAA-MM)", value=date.today().strftime("%Y-%m"))

rec = carregar("recorrentes")
lan = carregar("lancamentos")
lan_mes = lan[lan["mes"] == mes]

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
        enviar = st.form_submit_button("Salvar")
        if enviar and descricao:
            adicionar("lancamentos", [mes, date.today().isoformat(), tipo, descricao, valor])
            st.rerun()