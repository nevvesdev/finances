import html
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

COR_VERDE = "#22c55e"
COR_VERMELHA = "#ef4444"
COR_AMBAR = "#f59e0b"
COR_CINZA = "#64748b"
COR_FUNDO_CARD = "#181b22"
COR_BORDA = "#2a2f3c"
COR_TEXTO = "#e6e8ee"

def gerar_intervalo_meses(lan, mes, parsear_mes):
    referencia_fim = parsear_mes(mes)
    if referencia_fim is None:
        return []
    indice_fim = referencia_fim[0] * 12 + (referencia_fim[1] - 1)
    indices_validos = []
    if not lan.empty and "mes" in lan.columns:
        for valor_mes in lan["mes"].dropna().unique():
            referencia = parsear_mes(valor_mes)
            if referencia is not None:
                indices_validos.append(referencia[0] * 12 + (referencia[1] - 1))
    indice_inicio = min(indices_validos) if indices_validos else indice_fim
    if indice_inicio > indice_fim:
        indice_inicio = indice_fim
    lista_indices = list(range(indice_inicio, indice_fim + 1))[-12:]
    meses = []
    for indice in lista_indices:
        ano, mes_zero = divmod(indice, 12)
        meses.append(f"{ano:04d}-{mes_zero + 1:02d}")
    return meses

def calcular_serie_mensal(rec, lan, meses, somar_valores):
    registros = []
    acumulado = 0.0
    possui_mes = not lan.empty and "mes" in lan.columns
    for item_mes in meses:
        if possui_mes:
            lan_mes = lan[lan["mes"].astype(str).str.strip() == item_mes]
        else:
            lan_mes = lan.iloc[0:0]
        entradas_mes = somar_valores(rec, "entrada") + somar_valores(lan_mes, "entrada")
        despesas_mes = somar_valores(rec, "despesa") + somar_valores(lan_mes, "despesa")
        saldo_mes = entradas_mes - despesas_mes
        acumulado += saldo_mes
        registros.append(
            {
                "mes": item_mes,
                "entradas": entradas_mes,
                "despesas": despesas_mes,
                "saldo": saldo_mes,
                "saldo_acumulado": acumulado,
            }
        )
    return pd.DataFrame(registros)

def aplicar_tema_plotly(figura, eixo_valor="y"):
    figura.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        separators=",.",
        font=dict(family="sans-serif", color=COR_TEXTO),
        margin=dict(l=12, r=12, t=28, b=12),
        hoverlabel=dict(bgcolor=COR_FUNDO_CARD, bordercolor=COR_BORDA, font_color=COR_TEXTO),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
    )
    eixo_formatado = dict(
        tickprefix="R$ ",
        tickformat=",.2f",
        gridcolor=COR_BORDA,
        zerolinecolor=COR_BORDA,
    )
    if eixo_valor == "x":
        figura.update_xaxes(**eixo_formatado)
        figura.update_yaxes(showgrid=False)
    else:
        figura.update_yaxes(**eixo_formatado)
        figura.update_xaxes(type="category", showgrid=False)
    return figura

def grafico_entradas_despesas(serie, brl):
    if serie.empty:
        st.info("Informe um mês válido no formato AAAA-MM para visualizar os gráficos mensais.")
        return
    figura = go.Figure()
    figura.add_trace(
        go.Bar(
            name="Entradas",
            x=serie["mes"],
            y=serie["entradas"],
            marker_color=COR_VERDE,
            customdata=[brl(valor) for valor in serie["entradas"]],
            hovertemplate="<b>%{x}</b><br>Entradas: %{customdata}<extra></extra>",
        )
    )
    figura.add_trace(
        go.Bar(
            name="Despesas",
            x=serie["mes"],
            y=serie["despesas"],
            marker_color=COR_VERMELHA,
            customdata=[brl(valor) for valor in serie["despesas"]],
            hovertemplate="<b>%{x}</b><br>Despesas: %{customdata}<extra></extra>",
        )
    )
    figura.update_layout(barmode="group")
    aplicar_tema_plotly(figura, eixo_valor="y")
    st.plotly_chart(figura, use_container_width=True, config={"displayModeBar": False})

def grafico_despesas_categoria(rec, lan_mes, brl):
    falta_rec = len(rec.columns) > 0 and "categoria" not in rec.columns
    falta_lan = len(lan_mes.columns) > 0 and "categoria" not in lan_mes.columns
    if falta_rec or falta_lan:
        st.info("Adicione a coluna 'categoria' nas abas 'recorrentes' e 'lancamentos' para visualizar este gráfico.")
        return
    partes = []
    for tabela in (rec, lan_mes):
        if not tabela.empty and {"tipo", "valor", "categoria"}.issubset(tabela.columns):
            despesas = tabela[tabela["tipo"] == "despesa"][["categoria", "valor"]].copy()
            if not despesas.empty:
                partes.append(despesas)
    if not partes:
        st.info("Nenhuma despesa registrada neste mês.")
        return
    combinado = pd.concat(partes, ignore_index=True)
    combinado["categoria"] = combinado["categoria"].fillna("").astype(str).str.strip()
    combinado["categoria"] = combinado["categoria"].where(combinado["categoria"] != "", "Sem categoria")
    agrupado = (
        combinado.groupby("categoria", as_index=False)["valor"]
        .sum()
        .sort_values(by="valor", ascending=False)
    )
    agrupado = agrupado[agrupado["valor"] > 0]
    if agrupado.empty:
        st.info("Nenhuma despesa com valor positivo neste mês.")
        return
    figura = go.Figure(
        go.Bar(
            x=agrupado["valor"],
            y=agrupado["categoria"],
            orientation="h",
            marker_color=COR_VERMELHA,
            customdata=[brl(valor) for valor in agrupado["valor"]],
            hovertemplate="<b>%{y}</b><br>Despesas: %{customdata}<extra></extra>",
        )
    )
    figura.update_layout(showlegend=False)
    aplicar_tema_plotly(figura, eixo_valor="x")
    figura.update_yaxes(autorange="reversed")
    st.plotly_chart(figura, use_container_width=True, config={"displayModeBar": False})

def grafico_vencimentos_mes(rec, lan_mes, brl, classe_vencimento):
    partes = []
    colunas = ["descricao", "valor", "vencimento_data", "pago_status", "tipo"]
    for tabela in (rec, lan_mes):
        if not tabela.empty and set(colunas).issubset(tabela.columns):
            despesas = tabela[tabela["tipo"] == "despesa"][colunas].copy()
            if not despesas.empty:
                partes.append(despesas)
    if not partes:
        st.info("Nenhuma despesa registrada neste mês.")
        return
    combinado = pd.concat(partes, ignore_index=True)
    combinado = combinado[combinado["vencimento_data"].notna()].copy()
    if combinado.empty:
        st.info("Nenhuma despesa com vencimento definido neste mês.")
        return
    hoje = date.today()
    mapa_status = {
        "item-pago": ("Pago", COR_VERDE),
        "item-vencido": ("Vencido", COR_VERMELHA),
        "item-proximo": ("Vence em breve", COR_AMBAR),
        "": ("A vencer", COR_CINZA),
    }
    registros = []
    for _, linha in combinado.iterrows():
        classe, _ = classe_vencimento(
            linha["vencimento_data"],
            bool(linha["pago_status"]),
            linha["tipo"],
            hoje,
        )
        nome_status, cor = mapa_status.get(classe, ("A vencer", COR_CINZA))
        registros.append(
            {
                "data": linha["vencimento_data"],
                "data_texto": linha["vencimento_data"].strftime("%d/%m/%Y"),
                "status": nome_status,
                "cor": cor,
                "descricao": html.escape(str(linha["descricao"])),
                "valor": float(linha["valor"]),
            }
        )
    tabela_venc = pd.DataFrame(registros).sort_values(by="data")
    datas_ordenadas = list(dict.fromkeys(tabela_venc["data_texto"].tolist()))
    figura = go.Figure()
    ordem_status = [
        ("Pago", COR_VERDE),
        ("Vencido", COR_VERMELHA),
        ("Vence em breve", COR_AMBAR),
        ("A vencer", COR_CINZA),
    ]
    for nome_status, cor in ordem_status:
        sub = tabela_venc[tabela_venc["status"] == nome_status]
        if sub.empty:
            continue
        pontos_x = []
        pontos_y = []
        dicas = []
        for data_texto in datas_ordenadas:
            itens_data = sub[sub["data_texto"] == data_texto]
            if itens_data.empty:
                continue
            total_data = float(itens_data["valor"].sum())
            linhas_dica = [
                f"{item['descricao']}: {brl(item['valor'])}"
                for _, item in itens_data.iterrows()
            ]
            if len(linhas_dica) > 1:
                linhas_dica.append(f"<b>Total: {brl(total_data)}</b>")
            pontos_x.append(data_texto)
            pontos_y.append(total_data)
            dicas.append("<br>".join(linhas_dica))
        figura.add_trace(
            go.Bar(
                name=nome_status,
                x=pontos_x,
                y=pontos_y,
                marker_color=cor,
                customdata=dicas,
                hovertemplate="<b>%{x} • " + nome_status + "</b><br>%{customdata}<extra></extra>",
            )
        )
    figura.update_layout(barmode="stack")
    aplicar_tema_plotly(figura, eixo_valor="y")
    figura.update_xaxes(categoryorder="array", categoryarray=datas_ordenadas)
    st.plotly_chart(figura, use_container_width=True, config={"displayModeBar": False})

def grafico_saldo_acumulado(serie, brl):
    if serie.empty:
        st.info("Informe um mês válido no formato AAAA-MM para visualizar o saldo acumulado.")
        return
    saldo_final = float(serie["saldo_acumulado"].iloc[-1])
    cor_linha = COR_VERDE if saldo_final >= 0 else COR_VERMELHA
    cor_area = "rgba(34, 197, 94, 0.14)" if saldo_final >= 0 else "rgba(239, 68, 68, 0.14)"
    figura = go.Figure(
        go.Scatter(
            name="Saldo acumulado",
            x=serie["mes"],
            y=serie["saldo_acumulado"],
            mode="lines+markers",
            line=dict(color=cor_linha, width=3),
            marker=dict(color=cor_linha, size=8),
            fill="tozeroy",
            fillcolor=cor_area,
            customdata=[brl(valor) for valor in serie["saldo_acumulado"]],
            hovertemplate="<b>%{x}</b><br>Saldo acumulado: %{customdata}<extra></extra>",
        )
    )
    figura.add_hline(y=0, line_dash="dot", line_color=COR_BORDA)
    figura.update_layout(showlegend=False)
    aplicar_tema_plotly(figura, eixo_valor="y")
    st.plotly_chart(figura, use_container_width=True, config={"displayModeBar": False})

def renderizar_graficos(rec, lan, lan_mes, mes, brl, somar_valores, parsear_mes, classe_vencimento):
    meses = gerar_intervalo_meses(lan, mes, parsear_mes)
    serie = calcular_serie_mensal(rec, lan, meses, somar_valores) if meses else pd.DataFrame()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Entradas x despesas por mês")
        grafico_entradas_despesas(serie, brl)
    with col2:
        st.subheader("Despesas por categoria")
        grafico_despesas_categoria(rec, lan_mes, brl)
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Vencimentos do mês")
        grafico_vencimentos_mes(rec, lan_mes, brl, classe_vencimento)
    with col4:
        st.subheader("Saldo acumulado")
        grafico_saldo_acumulado(serie, brl)
