import calendar
import html
from datetime import date, timedelta

import gspread
import pandas as pd
import streamlit as st

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
.item-linha {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    background: #181b22;
    border: 1px solid #2a2f3c;
    border-radius: 12px;
    padding: 10px 14px;
    margin-bottom: 6px;
}
.item-vencido {
    background: rgba(239, 68, 68, 0.14);
    border-color: rgba(239, 68, 68, 0.6);
}
.item-proximo {
    background: rgba(245, 158, 11, 0.14);
    border-color: rgba(245, 158, 11, 0.6);
}
.item-pago {
    opacity: 0.72;
}
.item-meta {
    color: #9aa3b2;
    font-size: 0.85rem;
}
.item-vencido .item-data {
    color: #f87171;
    font-weight: 600;
}
.item-proximo .item-data {
    color: #fbbf24;
    font-weight: 600;
}
.item-selo {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    margin-left: 8px;
}
.item-vencido .item-selo {
    background: rgba(239, 68, 68, 0.25);
    color: #fca5a5;
}
.item-proximo .item-selo {
    background: rgba(245, 158, 11, 0.25);
    color: #fcd34d;
}
.item-pago .item-selo {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
}
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
    if resultado.empty:
        resultado["linha_planilha"] = pd.Series(dtype="int64")
        resultado["vencimento_efetivo"] = pd.Series(dtype="object")
        resultado["vencimento_data"] = pd.Series(dtype="object")
        resultado["pago_status"] = pd.Series(dtype="bool")
        return resultado
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

def parsear_mes(mes):
    partes = str(mes).strip().split("-")
    if len(partes) != 2:
        return None
    try:
        ano = int(partes[0])
        num_mes = int(partes[1])
        if 1 <= num_mes <= 12:
            return ano, num_mes
    except ValueError:
        return None
    return None

def parsear_meses_depois(valor):
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        return 0
    try:
        return int(float(texto))
    except ValueError:
        return 0

def calcular_vencimento(mes, dia_vencimento, meses_depois=0):
    referencia = parsear_mes(mes)
    if referencia is None:
        return None
    try:
        dia = int(float(str(dia_vencimento).strip()))
    except (TypeError, ValueError):
        return None
    if dia < 1:
        return None
    ano, num_mes = referencia
    deslocamento = parsear_meses_depois(meses_depois)
    total_meses = (ano * 12 + (num_mes - 1)) + deslocamento
    ano_destino, indice_mes = divmod(total_meses, 12)
    mes_destino = indice_mes + 1
    ultimo_dia = calendar.monthrange(ano_destino, mes_destino)[1]
    return date(ano_destino, mes_destino, min(dia, ultimo_dia))

def carregar_pagamentos():
    try:
        tabela = carregar("pagamentos")
    except gspread.WorksheetNotFound:
        return pd.DataFrame(columns=["mes", "item", "pago"])
    if tabela.empty and len(tabela.columns) == 0:
        return pd.DataFrame(columns=["mes", "item", "pago"])
    return tabela

def preparar_recorrentes(tabela, pagamentos, mes):
    resultado = tabela.copy()
    if resultado.empty:
        resultado["vencimento_data"] = pd.Series(dtype="object")
        resultado["pago_status"] = pd.Series(dtype="bool")
        return resultado
    if "dia_vencimento" not in resultado.columns:
        resultado["dia_vencimento"] = ""
    if "meses_depois" not in resultado.columns:
        resultado["meses_depois"] = 0
    resultado["vencimento_data"] = resultado.apply(
        lambda linha: calcular_vencimento(mes, linha["dia_vencimento"], linha["meses_depois"]),
        axis=1,
    )
    mapa_pagamentos = {}
    if not pagamentos.empty and {"mes", "item", "pago"}.issubset(pagamentos.columns):
        pagamentos_mes = pagamentos[pagamentos["mes"].astype(str).str.strip() == str(mes).strip()]
        for _, linha in pagamentos_mes.iterrows():
            chave = str(linha["item"]).strip()
            mapa_pagamentos[chave] = parsear_booleano(linha["pago"])
    descricoes = resultado["descricao"].astype(str).str.strip() if "descricao" in resultado.columns else ""
    resultado["pago_status"] = descricoes.map(lambda item: mapa_pagamentos.get(item, False))
    return resultado

def atualizar_pago_lancamento(linha, pago):
    aba = planilha().worksheet("lancamentos")
    cabecalho = aba.row_values(1)
    if "pago" not in cabecalho:
        st.error("Coluna 'pago' não encontrada na aba 'lancamentos'.")
        return False
    aba.update_cell(linha, cabecalho.index("pago") + 1, bool(pago))
    carregar.clear()
    return True

def atualizar_pago_recorrente(mes, item, pago):
    aba = planilha().worksheet("pagamentos")
    valores = aba.get_all_values()
    item_limpo = str(item).strip()
    mes_limpo = str(mes).strip()
    if not valores:
        aba.append_row(["mes", "item", "pago"], value_input_option="USER_ENTERED")
        aba.append_row([mes_limpo, item_limpo, bool(pago)], value_input_option="USER_ENTERED")
        carregar.clear()
        return True
    cabecalho = valores[0]
    if not {"mes", "item", "pago"}.issubset(cabecalho):
        st.error("Cabeçalho inválido na aba 'pagamentos'. Esperado: mes, item, pago.")
        return False
    idx_mes = cabecalho.index("mes")
    idx_item = cabecalho.index("item")
    idx_pago = cabecalho.index("pago")
    for num_linha, linha in enumerate(valores[1:], start=2):
        mes_linha = linha[idx_mes].strip() if len(linha) > idx_mes else ""
        item_linha = linha[idx_item].strip() if len(linha) > idx_item else ""
        if mes_linha == mes_limpo and item_linha == item_limpo:
            aba.update_cell(num_linha, idx_pago + 1, bool(pago))
            carregar.clear()
            return True
    nova_linha = [""] * len(cabecalho)
    nova_linha[idx_mes] = mes_limpo
    nova_linha[idx_item] = item_limpo
    nova_linha[idx_pago] = bool(pago)
    aba.append_row(nova_linha, value_input_option="USER_ENTERED")
    carregar.clear()
    return True

def somar_valores(tabela, tipo, pago=None):
    if tabela.empty or not {"tipo", "valor"}.issubset(tabela.columns):
        return 0.0
    filtro = tabela["tipo"] == tipo
    if pago is not None and "pago_status" in tabela.columns:
        filtro = filtro & (tabela["pago_status"] == pago)
    return float(tabela.loc[filtro, "valor"].sum())

mes = st.sidebar.text_input("Mês (AAAA-MM)", value=date.today().strftime("%Y-%m"))

pagamentos = carregar_pagamentos()
rec = preparar_recorrentes(carregar("recorrentes"), pagamentos, mes)
lan = preparar_lancamentos(carregar("lancamentos"))
lan_mes = lan[lan["mes"] == mes] if not lan.empty and "mes" in lan.columns else lan

entradas = somar_valores(rec, "entrada") + somar_valores(lan_mes, "entrada")
despesas = somar_valores(rec, "despesa") + somar_valores(lan_mes, "despesa")
saldo = entradas - despesas
a_pagar = somar_valores(rec, "despesa", pago=False) + somar_valores(lan_mes, "despesa", pago=False)
recebido = somar_valores(rec, "entrada", pago=True) + somar_valores(lan_mes, "entrada", pago=True)

st.title(f"Finanças • {mes}")

c1, c2, c3 = st.columns(3)
c1.metric("Entradas", brl(entradas))
c2.metric("Despesas", brl(despesas))
c3.metric("Saldo", brl(saldo))

c4, c5 = st.columns(2)
c4.metric("A pagar", brl(a_pagar))
c5.metric("Recebido", brl(recebido))

resumo, lancar = st.tabs(["Resumo", "Lançar"])

def classe_vencimento(vencimento, pago, hoje):
    if pago:
        return "item-pago", "Pago"
    if vencimento is None:
        return "", ""
    if vencimento < hoje:
        return "item-vencido", "Vencido"
    if vencimento <= hoje + timedelta(days=7):
        return "item-proximo", "Vence em breve"
    return "", ""

def renderizar_itens(tabela, prefixo_chave, ao_alternar):
    if tabela.empty:
        st.caption("Nenhum item encontrado.")
        return
    hoje = date.today()
    ordenada = tabela.sort_values(by="vencimento_data", na_position="last")
    for idx, linha in ordenada.iterrows():
        pago_atual = bool(linha["pago_status"])
        venc = linha["vencimento_data"]
        venc_texto = venc.strftime("%d/%m/%Y") if venc is not None else "Sem vencimento"
        classe_extra, rotulo = classe_vencimento(venc, pago_atual, hoje)
        descricao = html.escape(str(linha.get("descricao", "")))
        tipo = html.escape(str(linha.get("tipo", "")))
        valor = brl(float(linha.get("valor", 0)))
        selo = f'<span class="item-selo">{rotulo}</span>' if rotulo else ""
        col_check, col_cartao = st.columns([0.07, 0.93])
        with col_check:
            chave = f"{prefixo_chave}_{idx}_{pago_atual}"
            marcado = st.checkbox("Pago", value=pago_atual, key=chave, label_visibility="collapsed")
            if marcado != pago_atual and ao_alternar(linha, marcado):
                st.rerun()
        with col_cartao:
            st.markdown(
                f"""
                <div class="item-linha {classe_extra}">
                    <div>
                        <strong>{descricao}</strong>{selo}<br>
                        <span class="item-meta">{tipo} • Vencimento: <span class="item-data">{venc_texto}</span></span>
                    </div>
                    <div><strong>{valor}</strong></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with resumo:
    st.subheader("Recorrentes (todo mês)")
    renderizar_itens(
        rec,
        f"rec_{mes}",
        lambda linha, marcado: atualizar_pago_recorrente(mes, linha.get("descricao", ""), marcado),
    )
    st.subheader("Lançamentos do mês")
    renderizar_itens(
        lan_mes,
        f"lan_{mes}",
        lambda linha, marcado: atualizar_pago_lancamento(int(linha["linha_planilha"]), marcado),
    )

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