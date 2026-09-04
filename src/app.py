"""Interface Streamlit do McDuck AI."""

from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chat_actions import process_command
from database import FinanceDatabase
from finance import brl, calculate_goal, load_knowledge, local_answer, normalize, summarize_budget


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("MCDUCK_DB_PATH", str(BASE_DIR / "data" / "mcduck.db")))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss")
MOSS_PALETTE = [
    "#334A2C",
    "#45603A",
    "#587349",
    "#6B8658",
    "#7D9769",
    "#4A6650",
    "#5E7865",
    "#718B76",
]

SYSTEM_PROMPT = """Você é o McDuck AI, um agente de organização financeira pessoal.

OBJETIVO
Ajude o usuário a entender seu orçamento, controlar gastos e planejar metas.

REGRAS OBRIGATÓRIAS
1. Use somente os dados do contexto e os valores explicitamente informados pelo usuário.
2. Nunca invente renda, despesas, prazos, taxas ou resultados.
3. Explique cálculos de modo simples e identifique a origem dos valores usados.
4. Se faltarem dados, liste objetivamente o que falta e peça essas informações.
5. Não ensine, compare ou recomende investimentos e produtos financeiros, não prometa retornos e não substitua um profissional.
   A palavra "Investimentos" pode ser usada apenas como nome de uma categoria de planejamento definida pelo usuário.
6. Não solicite nem exponha senhas, tokens, CPF completo ou dados de outros clientes.
7. Recuse assuntos fora de orçamento, gastos, economia e planejamento de metas.
8. Termine, quando possível, com uma próxima ação prática, sem decidir pelo usuário.
9. Responda em português do Brasil, com linguagem amigável, direta e sem julgamento.
10. Quando uma solicitação de mudança estiver ambígua, peça o dado que falta antes de afirmar que algo foi alterado.
"""


@st.cache_data
def get_data():
    return load_knowledge(BASE_DIR)


@st.cache_resource
def get_database() -> FinanceDatabase:
    return FinanceDatabase(DB_PATH)


def ask_ollama(message: str, context: dict) -> str:
    """Envia perguntas abertas ao modelo local e falha de forma segura."""
    prompt = (
        f"{SYSTEM_PROMPT}\n\nCONTEXTO FINANCEIRO ATUAL:\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\nPERGUNTA DO USUÁRIO:\n{message}"
    )
    payload = json.dumps(
        {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
            answer = body.get("response", "").strip()
            if answer:
                return answer
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        pass
    return (
        "O assistente de linguagem não está disponível agora. Os cálculos de orçamento e metas "
        "continuam funcionando normalmente."
    )


def adjusted_summary(income: float, category_values: dict[str, float]) -> dict:
    """Monta o resumo a partir dos valores editáveis da sessão."""
    expenses = round(sum(category_values.values()), 2)
    committed = round(expenses / income * 100, 2) if income else None
    return {
        "receitas": round(income, 2),
        "despesas": expenses,
        "disponivel": round(income - expenses, 2),
        "percentual_comprometido": committed,
        "categorias": dict(sorted(category_values.items(), key=lambda item: item[1], reverse=True)),
    }


def pie_chart(categories: dict[str, float]) -> go.Figure:
    labels = [name.title() for name in categories]
    values = list(categories.values())
    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.54,
            sort=False,
            direction="clockwise",
            textinfo="percent",
            textposition="inside",
            insidetextfont={"color": "#FFFFFF", "size": 13},
            marker={"colors": MOSS_PALETTE, "line": {"color": "rgba(255,255,255,.45)", "width": 1}},
            hovertemplate="<b>%{label}</b><br>%{value:$,.2f}<br>%{percent}<extra></extra>",
        )
    )
    figure.update_layout(
        height=390,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "yanchor": "top", "y": -0.02, "xanchor": "center", "x": 0.5},
        uniformtext={"minsize": 10, "mode": "hide"},
    )
    return figure


def bar_chart(categories: dict[str, float]) -> go.Figure:
    ordered = sorted(categories.items(), key=lambda item: item[1])
    labels = [name.title() for name, _ in ordered]
    values = [value for _, value in ordered]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": "#526E46", "line": {"color": "#78916D", "width": 1}},
            text=[brl(value) for value in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:$,.2f}<extra></extra>",
        )
    )
    figure.update_layout(
        height=max(330, 55 * len(ordered)),
        margin={"l": 10, "r": 75, "t": 20, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"title": "Valor mensal", "showgrid": True, "gridcolor": "rgba(128,128,128,.16)"},
        yaxis={"title": "", "showgrid": False},
    )
    return figure


def metric_card(column, label: str, value: str, note: str) -> None:
    with column:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{html.escape(label)}</div>
                <div class="metric-value">{html.escape(value)}</div>
                <div class="metric-note">{html.escape(note)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_message(item: dict[str, str]) -> None:
    """Renderiza moeda sem permitir que o Markdown interprete R$ como fórmula."""
    role = item["role"]
    avatar = ":material/person:" if role == "user" else ":material/account_balance_wallet:"
    content = item["content"].replace("R$", "R\\$")
    with st.chat_message(role, avatar=avatar):
        st.markdown(content)


st.set_page_config(page_title="McDuck AI", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
      :root {
        --moss-900: #293d25;
        --moss-800: #344e2b;
        --moss-700: #45613a;
        --moss-500: #708962;
        --moss-200: #c4d0bd;
      }
      html, body, [class*="css"] {
        font-family: Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      }
      .block-container {max-width: 1240px; padding-top: 1.4rem; padding-bottom: 3rem;}
      .app-header {
        display: flex; align-items: center; gap: 1rem; min-height: 118px;
        padding: 1.35rem 1.55rem; margin-bottom: 1.35rem; border-radius: 18px;
        color: #f7faf5; background: linear-gradient(130deg, #293d25 0%, #3d5933 58%, #526e46 100%);
        box-shadow: 0 16px 42px rgba(28, 48, 24, .18);
      }
      .brand-mark {
        display: grid; place-items: center; flex: 0 0 58px; height: 58px; border-radius: 15px;
        color: #f7faf5; border: 1px solid rgba(255,255,255,.35); background: rgba(255,255,255,.10);
        font-size: 1.65rem; font-weight: 750; letter-spacing: -.06em;
      }
      .brand-copy {flex: 1; min-width: 0;}
      .brand-eyebrow {display: block; margin-bottom: .1rem; color: #d9e5d3 !important; font-size: .70rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; opacity: .92;}
      .brand-copy h1 {margin: .18rem 0 .08rem; color: #ffffff; font-size: clamp(1.75rem, 3vw, 2.35rem); line-height: 1.05; letter-spacing: -.035em;}
      .brand-copy p {margin: 0; color: rgba(255,255,255,.82); font-size: .95rem;}
      .header-status {display: flex; align-items: center; gap: .5rem; padding: .55rem .78rem; border-radius: 999px; background: rgba(255,255,255,.10); font-size: .76rem; white-space: nowrap;}
      .status-dot {width: 7px; height: 7px; border-radius: 50%; background: #b9d6a8; box-shadow: 0 0 0 4px rgba(185,214,168,.13);}
      .section-kicker {margin: 0 0 .18rem; color: var(--moss-500); font-size: .72rem; font-weight: 750; letter-spacing: .12em; text-transform: uppercase;}
      .section-title {margin: 0 0 1rem; color: var(--text-color); font-size: 1.35rem; letter-spacing: -.02em;}
      .metric-card {
        min-height: 132px; padding: 1.05rem 1.1rem; border: 1px solid rgba(82,110,70,.28);
        border-radius: 15px; background: rgba(82,110,70,.08); box-shadow: 0 8px 24px rgba(31,49,27,.06);
      }
      .metric-label {color: var(--text-color); opacity: .68; font-size: .77rem; font-weight: 650; letter-spacing: .035em; text-transform: uppercase;}
      .metric-value {margin: .42rem 0 .26rem; color: var(--text-color); font-size: clamp(1.45rem, 2.4vw, 2rem); font-weight: 700; letter-spacing: -.04em; white-space: nowrap;}
      .metric-note {color: var(--text-color); opacity: .58; font-size: .74rem;}
      .insight-card {height: 100%; min-height: 178px; padding: 1.25rem; border-left: 4px solid var(--moss-700); border-radius: 12px; background: rgba(82,110,70,.09);}
      .insight-label {color: var(--moss-500); font-size: .7rem; font-weight: 750; letter-spacing: .1em; text-transform: uppercase;}
      .insight-card h3 {margin: .42rem 0 .65rem; color: var(--text-color); font-size: 1.35rem;}
      .insight-card p {margin: 0 0 .55rem; color: var(--text-color); opacity: .78; line-height: 1.55;}
      .chat-intro {padding: 1.15rem 1.25rem; margin-bottom: 1rem; border: 1px solid rgba(82,110,70,.24); border-radius: 14px; background: linear-gradient(120deg, rgba(82,110,70,.12), rgba(82,110,70,.04));}
      .chat-intro h3 {margin: .35rem 0 .4rem; color: var(--text-color); font-size: 1.2rem;}
      .chat-intro p {margin: 0; color: var(--text-color); opacity: .72; line-height: 1.5;}
      .goal-card {padding: 1rem 1.1rem; margin: .7rem 0; border: 1px solid rgba(82,110,70,.25); border-radius: 13px; background: rgba(82,110,70,.06);}
      div[data-testid="stSidebar"] {min-width: 340px; border-right: 1px solid rgba(82,110,70,.18);}
      div[data-testid="stSidebar"] > div:first-child {width: 340px;}
      div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] h3 {letter-spacing: -.02em;}
      div[data-baseweb="tab-list"] {gap: .45rem; border-bottom: 1px solid rgba(128,128,128,.18);}
      div[data-baseweb="tab"] {min-height: 48px; padding-left: 1.15rem; padding-right: 1.15rem; font-size: .95rem; font-weight: 600;}
      [data-testid="stChatMessage"] {margin: .45rem 0; padding: .8rem 1rem; border: 1px solid rgba(82,110,70,.16); border-radius: 14px; background: rgba(82,110,70,.055);}
      .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        border-color: var(--moss-700); color: var(--text-color); border-radius: 9px;
      }
      .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        color: #ffffff; background: var(--moss-700); border-color: var(--moss-700);
      }
      [data-testid="stDataFrame"] {border: 1px solid rgba(82,110,70,.18); border-radius: 12px; overflow: hidden;}
      @media (max-width: 760px) {
        .app-header {align-items: flex-start; padding: 1.1rem;}
        .header-status {display: none;}
        .brand-mark {flex-basis: 48px; height: 48px;}
        .metric-card {min-height: 112px; margin-bottom: .3rem;}
      }
    </style>
    <header class="app-header">
      <div class="brand-mark">M</div>
      <div class="brand-copy">
        <div class="brand-eyebrow">Gestão financeira pessoal</div>
        <h1>McDuck AI</h1>
        <p>Clareza para organizar o presente e planejar os próximos passos.</p>
      </div>
      <div class="header-status"><span class="status-dot"></span>Planejamento mensal ativo</div>
    </header>
    """,
    unsafe_allow_html=True,
)

profile, transactions, history = get_data()
base_summary = summarize_budget(transactions)
db = get_database()
db.seed_defaults(
    base_summary["receitas"],
    base_summary["categorias"],
    profile.get("limites_mensais", {}),
)

if "expense_editor_version" not in st.session_state:
    st.session_state.expense_editor_version = 0
if "sync_income_from_database" in st.session_state:
    st.session_state.monthly_income = db.get_income()
    del st.session_state.sync_income_from_database
if "monthly_income" not in st.session_state:
    st.session_state.monthly_income = db.get_income()

with st.sidebar:
    st.markdown("## Planejamento mensal")
    st.caption("Ajuste os valores para refletir seu orçamento atual.")
    income = st.number_input(
        "Renda mensal",
        min_value=0.0,
        step=100.0,
        format="%.2f",
        key="monthly_income",
    )

    with st.expander("Adicionar tipo de gasto", expanded=False):
        with st.form("new_expense_form", clear_on_submit=True):
            new_category = st.text_input("Nome da categoria", placeholder="Ex.: Pets")
            new_amount = st.number_input("Valor mensal", min_value=0.0, step=10.0, format="%.2f")
            new_expense_type = st.selectbox("Tipo", ["Variável", "Fixa", "Planejamento"])
            add_expense = st.form_submit_button("Adicionar ao orçamento", type="primary", width="stretch")
        if add_expense:
            category = new_category.strip()
            if not category:
                st.error("Informe um nome para a categoria.")
            elif new_amount <= 0:
                st.error("Informe um valor maior que zero.")
            else:
                db.upsert_expense(
                    category,
                    float(new_amount),
                    new_expense_type,
                    add=True,
                    source="interface",
                )
                st.session_state.expense_editor_version += 1
                st.rerun()

    st.markdown("### Gastos por categoria")
    st.caption("As alterações são salvas automaticamente neste dispositivo.")
    stored_expenses = db.list_expenses()
    expense_frame = pd.DataFrame(
        [
            {
                "Categoria": row["category"],
                "Tipo": row["expense_type"],
                "Valor mensal": float(row["amount"]),
            }
            for row in stored_expenses
        ],
        columns=["Categoria", "Tipo", "Valor mensal"],
    )
    edited_expenses = st.data_editor(
        expense_frame,
        key=f"expense_editor_{st.session_state.expense_editor_version}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Categoria": st.column_config.TextColumn("Categoria", required=True, max_chars=40),
            "Tipo": st.column_config.SelectboxColumn(
                "Tipo", options=["Fixa", "Variável", "Planejamento"], required=True
            ),
            "Valor mensal": st.column_config.NumberColumn(
                "Valor mensal", min_value=0.0, step=10.0, format="R$ %.2f", required=True
            ),
        },
    )
    edited_records = [
        {
            "Categoria": str(row.get("Categoria", "")).strip(),
            "Tipo": str(row.get("Tipo", "Variável")),
            "Valor mensal": 0.0 if pd.isna(row.get("Valor mensal")) else float(row["Valor mensal"]),
        }
        for row in edited_expenses.to_dict("records")
        if str(row.get("Categoria", "")).strip()
    ]
    current_signature = [
        (row["category"], row["expense_type"], round(float(row["amount"]), 2))
        for row in stored_expenses
    ]
    edited_signature = [
        (row["Categoria"], row["Tipo"], round(float(row["Valor mensal"]), 2))
        for row in edited_records
    ]
    if current_signature != edited_signature:
        db.replace_expenses(edited_records)
        st.session_state.expense_editor_version += 1
        st.rerun()

    if round(float(income), 2) != round(db.get_income(), 2):
        db.set_income(float(income), source="interface")

    export_csv = edited_expenses.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Exportar orçamento",
        data=export_csv,
        file_name="orcamento-mensal.csv",
        mime="text/csv",
        width="stretch",
    )
    st.divider()
    use_ollama = st.toggle("Assistente de linguagem", value=True)
    st.caption(f"Modelo local: {OLLAMA_MODEL}")

stored_expenses = db.list_expenses()
categories = {row["category"]: float(row["amount"]) for row in stored_expenses}
summary = adjusted_summary(float(income), categories)
limits = db.list_limits()

tab_dashboard, tab_chat, tab_goals = st.tabs(["Visão geral", "Assistente", "Suas metas"])

with tab_dashboard:
    st.markdown('<p class="section-kicker">Resumo financeiro</p>', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">Seu mês em números</h2>', unsafe_allow_html=True)
    metric_columns = st.columns(4)
    metric_card(metric_columns[0], "Receita", brl(summary["receitas"]), "Total informado no mês")
    metric_card(metric_columns[1], "Despesas", brl(summary["despesas"]), "Soma de todas as categorias")
    balance_note = "Margem disponível" if summary["disponivel"] >= 0 else "Orçamento acima da renda"
    metric_card(metric_columns[2], "Disponível", brl(summary["disponivel"]), balance_note)
    committed = summary["percentual_comprometido"]
    metric_card(
        metric_columns[3],
        "Renda comprometida",
        f"{committed:.1f}%" if committed is not None else "Não calculado",
        "Relação entre despesas e renda",
    )

    st.write("")
    chart_column, insight_column = st.columns([1.75, 1], gap="large")
    with chart_column:
        with st.container(border=True):
            st.markdown("#### Distribuição dos gastos")
            if categories and summary["despesas"] > 0:
                pie_tab, bar_tab = st.tabs(["Gráfico de pizza", "Gráfico de barras"])
                with pie_tab:
                    st.plotly_chart(
                        pie_chart(categories),
                        width="stretch",
                        theme="streamlit",
                        config={"displayModeBar": False, "responsive": True},
                    )
                with bar_tab:
                    st.plotly_chart(
                        bar_chart(categories),
                        width="stretch",
                        theme="streamlit",
                        config={"displayModeBar": False, "responsive": True},
                    )
            else:
                st.info("Adicione pelo menos um gasto para visualizar a distribuição.")

    with insight_column:
        if categories:
            top_category, top_value = next(iter(summary["categorias"].items()))
            top_share = top_value / summary["despesas"] * 100 if summary["despesas"] else 0
            insight_title = html.escape(top_category.title())
            insight_text = (
                f"Esta categoria representa {top_share:.1f}% das despesas, com {brl(top_value)} no mês."
            )
        else:
            insight_title = "Orçamento ainda vazio"
            insight_text = "Adicione seus gastos para identificar os principais pontos do orçamento."
        if summary["disponivel"] < 0:
            action_text = f"As despesas ultrapassam a renda em {brl(abs(summary['disponivel']))}."
        else:
            action_text = f"A margem atual para metas e imprevistos é de {brl(summary['disponivel'])}."
        st.markdown(
            f"""
            <div class="insight-card">
                <div class="insight-label">Destaque do mês</div>
                <h3>{insight_title}</h3>
                <p>{html.escape(insight_text)}</p>
                <p>{html.escape(action_text)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown("#### Acompanhamento de limites")
    limit_rows = []
    for category, spent in summary["categorias"].items():
        limit = limits.get(normalize(category))
        if limit is None:
            status = "Sem limite definido"
            limit_display = "—"
        elif spent > float(limit):
            status = "Acima do limite"
            limit_display = brl(float(limit))
        else:
            status = "Dentro do limite"
            limit_display = brl(float(limit))
        limit_rows.append(
            {
                "Categoria": category.title(),
                "Gasto atual": brl(spent),
                "Limite": limit_display,
                "Situação": status,
            }
        )
    if limit_rows:
        st.dataframe(limit_rows, width="stretch", hide_index=True)
    else:
        st.caption("Nenhuma categoria adicionada.")

with tab_chat:
    st.markdown('<p class="section-kicker">Orientação financeira</p>', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">Converse com o McDuck AI</h2>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="chat-intro">
            <div class="insight-label">Assistente com ações</div>
            <h3>Converse e atualize seu planejamento</h3>
            <p>Peça para alterar renda, criar ou remover categorias, registrar aportes e reorganizar o orçamento. Solicitações ambíguas serão confirmadas antes da mudança.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quick_columns = st.columns(4)
    quick_message = None
    if quick_columns[0].button("Analisar orçamento", width="stretch"):
        quick_message = "Analise meu orçamento atual."
    if quick_columns[1].button("Reorganizar renda", width="stretch"):
        quick_message = "Reorganize minha renda da melhor forma possível."
    if quick_columns[2].button("Ver minhas metas", width="stretch"):
        quick_message = "Como estão minhas metas?"
    clear_chat = quick_columns[3].button("Limpar conversa", width="stretch")
    if clear_chat:
        db.clear_chat()
        st.rerun()

    stored_messages = db.list_messages()
    if not stored_messages:
        stored_messages = [
            {
                "role": "assistant",
                "content": (
                    "Olá. Posso analisar seu orçamento e também aplicar mudanças quando você pedir. "
                    "Experimente dizer: ‘Adicione R$ 300 em Pets’ ou ‘Minha renda passou para R$ 6.000’."
                ),
            }
        ]

    for item in stored_messages:
        render_chat_message(item)

    typed_message = st.chat_input("Digite uma pergunta ou alteração para o seu orçamento")
    message = typed_message or quick_message
    if message:
        db.save_message("user", message)
        stored_goals = db.list_goals()
        user_profile = {
            **profile,
            "metas": [
                {
                    "meta": goal["name"],
                    "valor_necessario": goal["target"],
                    "valor_atual": goal["current"],
                    "prazo": goal["deadline"],
                }
                for goal in stored_goals
            ],
            "limites_mensais": limits,
        }
        command = process_command(message, db, summary["disponivel"])
        if command.handled:
            answer = command.message
        else:
            answer = local_answer(message, user_profile, summary)
        if not command.handled and answer is None:
            if use_ollama:
                context = {
                    "resumo_orcamento": summary,
                    "despesas_com_tipo": db.list_expenses(),
                    "limites_mensais": limits,
                    "metas": stored_goals,
                    "atendimentos_anteriores": history,
                }
                with st.spinner("Analisando seu contexto financeiro..."):
                    answer = ask_ollama(message, context)
            else:
                answer = (
                    "Ative o assistente de linguagem na barra lateral para perguntas abertas. "
                    "Os cálculos de orçamento e metas permanecem disponíveis."
                )
        db.save_message("assistant", answer)
        if command.changed:
            st.session_state.expense_editor_version += 1
        if command.income_changed:
            st.session_state.sync_income_from_database = True
        st.rerun()

    recent_changes = db.list_changes(6)
    if recent_changes:
        with st.expander("Alterações salvas recentemente"):
            for change in recent_changes:
                action = change["action"].replace("_", " ").title()
                time_label = change["created_at"].replace("T", " ")
                st.caption(f"{time_label} — {action}")

with tab_goals:
    st.markdown('<p class="section-kicker">Planejamento</p>', unsafe_allow_html=True)
    st.markdown('<h2 class="section-title">Suas metas</h2>', unsafe_allow_html=True)
    form_column, overview_column = st.columns([1, 1.35], gap="large")

    with form_column:
        with st.container(border=True):
            st.markdown("#### Adicionar uma meta")
            with st.form("goal_form", clear_on_submit=True):
                goal_name = st.text_input("Nome da meta", placeholder="Ex.: Reserva de emergência")
                target = st.number_input("Valor desejado", min_value=0.0, step=100.0, format="%.2f")
                current = st.number_input("Valor já reservado", min_value=0.0, step=100.0, format="%.2f")
                default_deadline = date(date.today().year + 1, date.today().month, 1)
                deadline = st.date_input("Prazo", value=default_deadline, min_value=date.today())
                add_goal = st.form_submit_button("Adicionar meta", type="primary", width="stretch")
            if add_goal:
                if not goal_name.strip():
                    st.error("Informe um nome para a meta.")
                elif target <= 0:
                    st.error("Informe um valor desejado maior que zero.")
                else:
                    db.add_goal(
                        goal_name,
                        float(target),
                        float(current),
                        deadline.strftime("%Y-%m"),
                        source="interface",
                    )
                    st.rerun()

    with overview_column:
        st.markdown("#### Metas em andamento")
        stored_goals = db.list_goals()
        if not stored_goals:
            st.markdown(
                """
                <div class="insight-card">
                    <div class="insight-label">Comece por um objetivo</div>
                    <h3>Nenhuma meta cadastrada</h3>
                    <p>Defina um valor, quanto já foi reservado e o prazo. O cálculo mensal será feito sem presumir rendimentos.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            goals_to_remove = []
            for goal_data in stored_goals:
                calculation = calculate_goal(
                    goal_data["target"],
                    goal_data["current"],
                    goal_data["deadline"],
                )
                progress = min(
                    1.0,
                    goal_data["current"] / goal_data["target"]
                    if goal_data["target"]
                    else 0,
                )
                with st.container(border=True):
                    title_col, remove_col = st.columns([5, 1])
                    title_col.markdown(f"**{html.escape(goal_data['name'])}**")
                    if remove_col.button("Remover", key=f"remove_goal_{goal_data['id']}"):
                        goals_to_remove.append(goal_data["id"])
                    st.progress(progress, text=f"{progress * 100:.0f}% concluído")
                    data_col1, data_col2, data_col3 = st.columns(3)
                    data_col1.caption("Valor da meta")
                    data_col1.write(brl(goal_data["target"]))
                    data_col2.caption("Falta reservar")
                    data_col2.write(brl(calculation["valor_faltante"]))
                    data_col3.caption("Reserva mensal")
                    if calculation["prazo_vencido"]:
                        data_col3.write("Prazo vencido")
                    elif calculation["valor_faltante"] == 0:
                        data_col3.write("Meta concluída")
                    else:
                        data_col3.write(brl(calculation["economia_mensal"]))
                    if (
                        not calculation["prazo_vencido"]
                        and calculation["economia_mensal"] > max(summary["disponivel"], 0)
                    ):
                        st.warning("A reserva mensal calculada supera a margem disponível no orçamento atual.")
            for goal_id in goals_to_remove:
                db.remove_goal(goal_id)
            if goals_to_remove:
                st.rerun()

st.caption(
    "O McDuck AI apoia a organização financeira e não substitui orientação profissional. "
    "Não compartilhe senhas, tokens ou dados bancários sensíveis."
)
