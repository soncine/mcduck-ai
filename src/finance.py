"""Cálculos financeiros determinísticos usados pelo McDuck AI."""

from __future__ import annotations

import csv
import json
import math
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def load_knowledge(base_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Carrega somente os dados necessários à organização financeira."""
    data_dir = base_dir / "data"
    with (data_dir / "perfil_investidor.json").open(encoding="utf-8") as file:
        profile = json.load(file)

    with (data_dir / "transacoes.csv").open(encoding="utf-8", newline="") as file:
        transactions = list(csv.DictReader(file))

    with (data_dir / "historico_atendimento.csv").open(encoding="utf-8", newline="") as file:
        history = list(csv.DictReader(file))

    return profile, transactions, history


def summarize_budget(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Soma receitas e despesas e agrupa saídas por categoria."""
    income = 0.0
    expenses = 0.0
    categories: dict[str, float] = defaultdict(float)

    for item in transactions:
        value = float(item["valor"])
        if item["tipo"].strip().lower() == "entrada":
            income += value
        elif item["tipo"].strip().lower() == "saida":
            expenses += value
            categories[item["categoria"].strip().lower()] += value

    available = income - expenses
    committed = (expenses / income * 100) if income else None
    return {
        "receitas": round(income, 2),
        "despesas": round(expenses, 2),
        "disponivel": round(available, 2),
        "percentual_comprometido": round(committed, 2) if committed is not None else None,
        "categorias": dict(sorted(categories.items(), key=lambda item: item[1], reverse=True)),
    }


def compare_limits(category_totals: dict[str, float], limits: dict[str, float]) -> list[dict[str, Any]]:
    """Compara gastos observados com limites informados pelo usuário."""
    result = []
    for category in sorted(set(category_totals) | set(limits)):
        spent = float(category_totals.get(category, 0))
        limit = float(limits.get(category, 0))
        difference = limit - spent
        result.append(
            {
                "categoria": category,
                "gasto": round(spent, 2),
                "limite": round(limit, 2),
                "diferenca": round(difference, 2),
                "status": "acima" if limit and spent > limit else "dentro",
            }
        )
    return result


def months_until(deadline: str, today: date | None = None) -> int:
    """Retorna meses restantes até AAAA-MM; zero indica prazo vencido."""
    reference = today or date.today()
    year, month = (int(part) for part in deadline.split("-"))
    if month < 1 or month > 12:
        raise ValueError("Mês inválido")
    return max(0, (year - reference.year) * 12 + month - reference.month)


def calculate_goal(target: float, current: float, deadline: str, today: date | None = None) -> dict[str, Any]:
    """Calcula o aporte mensal necessário, sem supor rentabilidade."""
    missing = max(0.0, float(target) - float(current))
    months = months_until(deadline, today)
    monthly = math.ceil((missing / months) * 100) / 100 if missing and months else 0.0
    return {
        "valor_faltante": round(missing, 2),
        "meses_restantes": months,
        "economia_mensal": monthly,
        "prazo_vencido": bool(missing and months == 0),
    }


def normalize(text: str) -> str:
    """Normaliza texto para a classificação simples de intenção."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def brl(value: float) -> str:
    """Formata um número em Real sem depender do locale do sistema."""
    formatted = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


def budget_answer(summary: dict[str, Any], limits: dict[str, float]) -> str:
    """Gera uma resposta auditável sobre o orçamento carregado."""
    categories = summary["categorias"]
    lines = [
        f"No período carregado, as receitas somam **{brl(summary['receitas'])}** e as despesas "
        f"somam **{brl(summary['despesas'])}**. O valor disponível é **{brl(summary['disponivel'])}**."
    ]
    if summary["percentual_comprometido"] is not None:
        lines.append(f"Isso compromete **{summary['percentual_comprometido']:.1f}%** da renda registrada.")
    if categories:
        top_category, top_value = next(iter(categories.items()))
        lines.append(f"A maior categoria é **{top_category.title()}**, com **{brl(top_value)}**.")

    exceeded = [item for item in compare_limits(categories, limits) if item["status"] == "acima"]
    if exceeded:
        details = ", ".join(
            f"{item['categoria']} ({brl(abs(item['diferenca']))} acima)" for item in exceeded
        )
        lines.append(f"Limites ultrapassados: {details}.")
    else:
        lines.append("Nenhum dos limites cadastrados foi ultrapassado.")

    lines.append("**Próxima ação:** revise primeiro a maior categoria antes de definir um novo corte.")
    return "\n\n".join(lines)


def goals_answer(goals: list[dict[str, Any]], available: float) -> str:
    """Gera análise das metas sem considerar juros ou retornos futuros."""
    if not goals:
        return "Não há metas cadastradas. Informe nome, valor, valor já guardado e prazo para eu calcular."

    paragraphs = []
    for goal in goals:
        result = calculate_goal(goal["valor_necessario"], goal.get("valor_atual", 0), goal["prazo"])
        name = goal["meta"]
        if result["valor_faltante"] == 0:
            paragraphs.append(f"**{name}:** meta já alcançada com o valor informado.")
        elif result["prazo_vencido"]:
            paragraphs.append(
                f"**{name}:** faltam {brl(result['valor_faltante'])}, mas o prazo informado já venceu. "
                "Defina uma nova data para recalcular."
            )
        else:
            feasibility = (
                "cabe no valor disponível atual"
                if result["economia_mensal"] <= max(available, 0)
                else "é maior que o valor disponível atual"
            )
            paragraphs.append(
                f"**{name}:** faltam {brl(result['valor_faltante'])}. Para chegar até {goal['prazo']}, "
                f"seriam necessários **{brl(result['economia_mensal'])} por mês** por "
                f"{result['meses_restantes']} meses; esse valor {feasibility}."
            )
    paragraphs.append("**Próxima ação:** escolha uma meta prioritária e reserve o valor mensal logo após receber a renda.")
    return "\n\n".join(paragraphs)


def local_answer(message: str, profile: dict[str, Any], summary: dict[str, Any]) -> str | None:
    """Responde intenções críticas localmente; retorna None quando a LLM pode ajudar."""
    intent = normalize(message)
    if any(term in intent for term in ("senha", "token", "cpf", "outro cliente", "dados bancarios")):
        return (
            "Não tenho acesso a senhas, tokens ou dados de outros clientes e não devo receber esse tipo de dado. "
            "Posso ajudar usando apenas valores financeiros não sensíveis que você decidir informar."
        )
    if any(term in intent for term in ("investir", "investimento", "acao", "acoes", "cripto", "retorno garantido")):
        return (
            "Não ensino, comparo ou recomendo investimentos e produtos financeiros. Posso usar "
            "‘Investimentos’ apenas como uma categoria do orçamento quando você indicar o valor."
        )
    if any(term in intent for term in ("meta", "objetivo", "guardar", "economizar por mes")):
        return goals_answer(profile.get("metas", []), summary["disponivel"])
    if any(term in intent for term in ("orcamento", "gasto", "despesa", "saldo", "renda", "categoria")):
        return budget_answer(summary, profile.get("limites_mensais", {}))
    if any(term in intent for term in ("tempo", "clima", "futebol", "receita de bolo")):
        return (
            "Esse assunto está fora do meu escopo. Sou especializado em organização financeira pessoal, "
            "controle de gastos e planejamento de metas."
        )
    return None
