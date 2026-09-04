"""Interpretação segura de comandos financeiros enviados pelo chat."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from database import FinanceDatabase
from finance import brl, normalize


MONEY_PATTERN = (
    r"(?:R\$\s*)?"
    r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?|\d+\.\d{1,2})"
    r"(?![\d.,])"
)


@dataclass
class CommandResult:
    handled: bool
    message: str = ""
    changed: bool = False
    income_changed: bool = False


def parse_money(raw_value: str) -> float:
    value = raw_value.strip().replace("R$", "").replace(" ", "")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif value.count(".") > 1:
        value = value.replace(".", "")
    elif "." in value and len(value.rsplit(".", 1)[1]) == 3:
        value = value.replace(".", "")
    return float(value)


def first_amount(message: str) -> float | None:
    match = re.search(MONEY_PATTERN, message, flags=re.IGNORECASE)
    return parse_money(match.group(1)) if match else None


def clean_category(value: str) -> str:
    value = re.sub(MONEY_PATTERN, "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\b(?:por mês|mensais|mensal|como gasto|como despesa|na tabela|no orçamento|por favor)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip(" .,!?:;-").title()[:40]


def find_category_after_connector(message: str) -> str:
    patterns = [
        r"\b(?:na|em)\s+categoria\s+(.+)$",
        r"\b(?:em|para)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            category = clean_category(match.group(1))
            if category:
                return category
    return ""


def parse_limit_change(message: str) -> tuple[str, float] | None:
    """Extrai categoria e valor de comandos comuns de criação ou alteração de limite."""
    category_first = re.search(
        rf"\b(?:defina|adicione|crie|coloque|estabele[çc]a|ajuste|altere|mude)\s+"
        rf"(?:(?:um|o)\s+)?limite\s+(?:de|da|do|para|em|na categoria)\s+(.+?)\s+"
        rf"(?:em|para|de|no valor de)\s+{MONEY_PATTERN}",
        message,
        flags=re.IGNORECASE,
    )
    if category_first:
        category = clean_category(category_first.group(1))
        amount = parse_money(category_first.group(2))
        return (category, amount) if category else None

    amount_first = re.search(
        rf"\b(?:defina|adicione|crie|coloque|estabele[çc]a|ajuste|altere|mude)\s+"
        rf"(?:(?:um|o)\s+)?limite\s+(?:de|em|no valor de)?\s*{MONEY_PATTERN}\s+"
        rf"(?:em|para|na categoria|à categoria|a categoria)\s+(.+)$",
        message,
        flags=re.IGNORECASE,
    )
    if amount_first:
        amount = parse_money(amount_first.group(1))
        category = clean_category(amount_first.group(2))
        return (category, amount) if category else None
    return None


def _reorganize_budget(db: FinanceDatabase, income: float, mention_investment: bool) -> CommandResult:
    expenses = db.list_expenses()
    planning_names = {"reserva e metas", "flexibilidade", "margem de seguranca", "investimentos"}
    operational = [row for row in expenses if normalize(row["category"]) not in planning_names]
    fixed = [row for row in operational if row["expense_type"] == "Fixa"]
    non_fixed = [row for row in operational if row["expense_type"] != "Fixa"]
    fixed_total = sum(float(row["amount"]) for row in fixed)
    variable_total = sum(float(row["amount"]) for row in non_fixed)

    if fixed_total >= income:
        return CommandResult(
            True,
            f"A renda de {brl(income)} não cobre as despesas fixas de {brl(fixed_total)}. "
            "Antes de reorganizar, preciso saber quais despesas fixas podem ser revistas.",
        )
    if fixed_total + variable_total > income:
        deficit = fixed_total + variable_total - income
        return CommandResult(
            True,
            f"Mantendo as despesas fixas e variáveis atuais, faltariam {brl(deficit)}. "
            "Quais categorias variáveis você autoriza reduzir primeiro?",
        )

    for row in expenses:
        if normalize(row["category"]) in planning_names:
            db.remove_expense(row["category"], source="chat_reorganizacao")

    remaining = income - fixed_total - variable_total
    if remaining <= 0:
        return CommandResult(
            True,
            "A renda já está totalmente comprometida com as categorias atuais. "
            "Diga quais gastos variáveis podem ser reduzidos para criar margem.",
        )

    priority_name = "Investimentos" if mention_investment else "Reserva e metas"
    allocations = [
        (priority_name, round(remaining * 0.60, 2)),
        ("Flexibilidade", round(remaining * 0.20, 2)),
        ("Margem de segurança", round(remaining * 0.20, 2)),
    ]
    rounding_difference = round(remaining - sum(value for _, value in allocations), 2)
    allocations[-1] = (allocations[-1][0], allocations[-1][1] + rounding_difference)
    for category, amount in allocations:
        db.upsert_expense(category, amount, "Planejamento", source="chat_reorganizacao")

    investment_note = (
        " Usei ‘Investimentos’ somente como categoria de destino; não selecionei nem avaliei produtos."
        if mention_investment
        else ""
    )
    return CommandResult(
        True,
        (
            f"Reorganizei a renda de {brl(income)} preservando {brl(fixed_total)} em despesas fixas "
            f"e {brl(variable_total)} nas demais despesas atuais. Dos {brl(remaining)} restantes, "
            f"destinei 60% para {priority_name}, 20% para Flexibilidade e 20% para Margem de segurança."
            f"{investment_note} Se sua prioridade for outra, diga qual categoria deve receber mais ou menos."
        ),
        changed=True,
    )


def process_command(
    message: str,
    db: FinanceDatabase,
    available: float,
) -> CommandResult:
    """Executa comandos explícitos e pede contexto quando não há base segura."""
    text = message.strip()
    intent = normalize(text)
    if not text:
        return CommandResult(False)

    investment_terms = ("investimento", "investimentos", "acao", "acoes", "cripto", "tesouro", "cdb")
    change_terms = (
        "adicione",
        "adicionar",
        "coloque",
        "colocar",
        "alocar",
        "destinar",
        "incluir",
        "inclua",
        "registre",
        "crie",
        "defina",
        "estabeleca",
        "mude",
        "altere",
        "ajuste",
        "remova",
        "exclua",
        "apague",
        "divida",
        "dividir",
        "distribua",
        "reorganize",
    )

    # A palavra investimento é aceita como rótulo de orçamento, mas não como conteúdo educativo.
    is_budget_change = any(term in intent for term in change_terms)
    is_investment_topic = any(
        re.search(rf"\b{re.escape(term)}\b", intent) for term in investment_terms
    )
    if is_investment_topic and not is_budget_change:
        return CommandResult(
            True,
            "Não ensino, comparo ou recomendo investimentos e produtos financeiros. Posso, porém, "
            "usar ‘Investimentos’ como uma categoria do seu planejamento quando você indicar um valor.",
        )

    # Alocar todo o saldo em uma categoria é uma ordem explícita e pode ser aplicada imediatamente.
    if (
        ("todo" in intent or "tudo" in intent)
        and ("sobra" in intent or "disponivel" in intent or "restante" in intent)
        and is_budget_change
    ):
        category = find_category_after_connector(text)
        if not category and is_investment_topic:
            category = "Investimentos"
        if not category:
            return CommandResult(True, "Em qual categoria você quer colocar o valor disponível?")
        if normalize(category) in {"investimento", "investimentos"}:
            category = "Investimentos"
        if available <= 0:
            return CommandResult(True, "Não há saldo disponível positivo para alocar neste momento.")
        db.upsert_expense(category, available, "Planejamento", add=True, source="chat")
        return CommandResult(
            True,
            f"Adicionei {brl(available)} à categoria {category}. O orçamento foi atualizado e o saldo disponível ficou zerado.",
            changed=True,
        )

    income_match = re.search(
        rf"\b(?:renda|sal[áa]rio|recebendo|receber|ganhando|ganhar)\b.{{0,30}}?{MONEY_PATTERN}",
        text,
        flags=re.IGNORECASE,
    )
    new_income = parse_money(income_match.group(1)) if income_match else None
    wants_reorganization = any(term in intent for term in ("dividir", "divida", "distribuir", "distribua", "reorganizar", "reorganize", "melhor forma"))
    if new_income is not None and ("comecei" in intent or "minha renda" in intent or wants_reorganization):
        db.set_income(new_income, source="chat")
        if wants_reorganization:
            result = _reorganize_budget(db, new_income, is_investment_topic)
            result.income_changed = True
            result.changed = result.changed or True
            return result
        return CommandResult(
            True,
            f"Atualizei sua renda mensal para {brl(new_income)}.",
            changed=True,
            income_changed=True,
        )

    if wants_reorganization:
        return _reorganize_budget(db, db.get_income(), is_investment_topic)

    remove_limit_match = re.search(
        r"\b(?:remova|exclua|apague|retire)\s+(?:o\s+)?limite\s+"
        r"(?:de|da|do|para|em|na categoria)\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if remove_limit_match:
        category = clean_category(remove_limit_match.group(1))
        if db.remove_limit(category, source="chat"):
            return CommandResult(
                True,
                f"Removi o limite da categoria {category}.",
                changed=True,
            )
        return CommandResult(
            True,
            f"Não encontrei um limite para a categoria {category}. Qual limite devo remover?",
        )

    limit_change = parse_limit_change(text)
    if limit_change:
        category, amount = limit_change
        if amount <= 0:
            return CommandResult(True, "O limite precisa ser maior que zero.")
        db.upsert_limit(category, amount, source="chat")
        return CommandResult(
            True,
            f"Defini o limite mensal de {category} em {brl(amount)}.",
            changed=True,
        )

    if "limite" in intent and any(
        term in intent
        for term in ("defina", "adicione", "crie", "coloque", "estabeleca", "ajuste", "altere", "mude")
    ):
        if first_amount(text) is None:
            return CommandResult(True, "Qual valor mensal você quer definir para esse limite?")
        return CommandResult(True, "Para qual categoria você quer definir esse limite?")

    # Exemplo: “altere Alimentação para R$ 650”.
    update_match = re.search(
        rf"\b(?:mude|altere|ajuste|defina)\s+(?:o gasto\s+|a categoria\s+)?(.+?)\s+(?:para|em)\s+{MONEY_PATTERN}",
        text,
        flags=re.IGNORECASE,
    )
    if update_match:
        category = clean_category(update_match.group(1))
        amount = parse_money(update_match.group(2))
        if category:
            expense_type = "Fixa" if "fix" in intent else "Variável"
            db.upsert_expense(category, amount, expense_type, source="chat")
            return CommandResult(
                True,
                f"Atualizei {category} para {brl(amount)} por mês.",
                changed=True,
            )

    # Exemplo: “adicione R$ 300 em Pets”.
    if any(
        term in intent
        for term in (
            "adicione",
            "adicionar",
            "coloque",
            "colocar",
            "alocar",
            "destinar",
            "inclua",
            "incluir",
            "registre",
        )
    ):
        amount = first_amount(text)
        category = find_category_after_connector(text)
        if amount is not None and category and "meta" not in intent and "aporte" not in intent:
            expense_type = "Fixa" if "fix" in intent else "Variável"
            if is_investment_topic:
                expense_type = "Planejamento"
            db.upsert_expense(category, amount, expense_type, add=True, source="chat")
            return CommandResult(
                True,
                f"Adicionei {brl(amount)} à categoria {category}.",
                changed=True,
            )

    remove_match = re.search(
        r"\b(?:remova|exclua|apague|retire)\s+(?:o gasto\s+|a categoria\s+)?(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if remove_match:
        category = clean_category(remove_match.group(1))
        if db.remove_expense(category, source="chat"):
            return CommandResult(True, f"Removi a categoria {category} do orçamento.", changed=True)
        return CommandResult(True, f"Não encontrei uma categoria chamada {category}. Qual categoria devo remover?")

    contribution_match = re.search(
        rf"\b(?:aporte|depositei|guardei|reservei|adicione)\b.*?{MONEY_PATTERN}.*?\b(?:na|para a|em)\s+(?:meta\s+)?(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if contribution_match and (
        "aporte" in intent or "na meta" in intent or "para a meta" in intent or "em meta" in intent
    ):
        amount = parse_money(contribution_match.group(1))
        goal_name = clean_category(contribution_match.group(2))
        goal = db.add_goal_contribution(goal_name, amount, source="chat")
        if goal:
            return CommandResult(
                True,
                f"Registrei {brl(amount)} na meta {goal['name']}. O total reservado agora é {brl(goal['current'])}.",
                changed=True,
            )
        return CommandResult(True, "Não identifiquei uma única meta com esse nome. Informe o nome exatamente como aparece em Suas metas.")

    goal_date_match = re.search(r"(\d{4}-\d{2}|\d{1,2}/\d{4})", text)
    if "meta" in intent and any(term in intent for term in ("crie", "adicione", "adicionar", "quero")):
        amount_text = text.replace(goal_date_match.group(1), "") if goal_date_match else text
        amount = first_amount(amount_text)
        if amount is None or goal_date_match is None:
            return CommandResult(True, "Para criar a meta, informe o nome, o valor desejado e o prazo, por exemplo: ‘Crie a meta Viagem de R$ 6.000 para 12/2027’." )
        raw_deadline = goal_date_match.group(1)
        if "/" in raw_deadline:
            month, year = raw_deadline.split("/")
            deadline = f"{year}-{int(month):02d}"
        else:
            deadline = raw_deadline
        if not 1 <= int(deadline.split("-")[1]) <= 12 or deadline < date.today().strftime("%Y-%m"):
            return CommandResult(True, "O prazo da meta precisa ser um mês válido e não pode estar no passado.")
        name_match = re.search(r"\bmeta\s+(.+?)(?:\s+de\s+|\s+no valor de\s+)", text, flags=re.IGNORECASE)
        goal_name = clean_category(name_match.group(1)) if name_match else "Nova meta"
        db.add_goal(goal_name, amount, 0, deadline, source="chat")
        return CommandResult(
            True,
            f"Criei a meta {goal_name}, no valor de {brl(amount)}, com prazo em {deadline}.",
            changed=True,
        )

    return CommandResult(False)
