"""Persistência SQLite para orçamento, metas e conversas."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from finance import normalize


class FinanceDatabase:
    """Camada pequena de persistência, sem manter conexões globais abertas."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    amount REAL NOT NULL CHECK (amount >= 0),
                    expense_type TEXT NOT NULL DEFAULT 'Variável',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS category_limits (
                    category TEXT PRIMARY KEY COLLATE NOCASE,
                    amount REAL NOT NULL CHECK (amount > 0),
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    target REAL NOT NULL CHECK (target > 0),
                    current REAL NOT NULL DEFAULT 0 CHECK (current >= 0),
                    deadline TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS change_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def seed_defaults(
        self,
        income: float,
        categories: dict[str, float],
        limits: dict[str, float] | None = None,
    ) -> None:
        """Cria valores iniciais somente no primeiro uso."""
        with self._connect() as connection:
            setting = connection.execute("SELECT 1 FROM settings WHERE key = 'monthly_income'").fetchone()
            if setting is None:
                connection.execute(
                    "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
                    ("monthly_income", str(float(income)), self._now()),
                )

            seeded = connection.execute("SELECT 1 FROM settings WHERE key = 'defaults_seeded'").fetchone()
            if seeded is None:
                fixed_categories = {"moradia", "educacao"}
                for category, amount in categories.items():
                    expense_type = "Fixa" if normalize(category) in fixed_categories else "Variável"
                    connection.execute(
                        "INSERT INTO expenses(category, amount, expense_type, updated_at) VALUES (?, ?, ?, ?)",
                        (category.title(), float(amount), expense_type, self._now()),
                    )
                connection.execute(
                    "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
                    ("defaults_seeded", "1", self._now()),
                )

            limits_seeded = connection.execute(
                "SELECT 1 FROM settings WHERE key = 'limits_seeded'"
            ).fetchone()
            if limits is not None and limits_seeded is None:
                for category, amount in limits.items():
                    if float(amount) <= 0:
                        continue
                    connection.execute(
                        "INSERT OR IGNORE INTO category_limits(category, amount, updated_at) VALUES (?, ?, ?)",
                        (category.strip().title(), float(amount), self._now()),
                    )
                connection.execute(
                    "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
                    ("limits_seeded", "1", self._now()),
                )

    def get_income(self) -> float:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = 'monthly_income'").fetchone()
        return float(row["value"]) if row else 0.0

    def set_income(self, value: float, source: str = "interface") -> None:
        value = max(0.0, float(value))
        previous = self.get_income()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value, updated_at) VALUES ('monthly_income', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (str(value), self._now()),
            )
        if round(previous, 2) != round(value, 2):
            self.log_change("renda_atualizada", {"de": previous, "para": value, "origem": source})

    def list_expenses(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, category, amount, expense_type FROM expenses ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_expense(
        self,
        category: str,
        amount: float,
        expense_type: str = "Variável",
        *,
        add: bool = False,
        source: str = "interface",
    ) -> None:
        category = category.strip()[:40]
        if not category:
            raise ValueError("A categoria é obrigatória")
        amount = max(0.0, float(amount))
        expense_type = expense_type if expense_type in {"Fixa", "Variável", "Planejamento"} else "Variável"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT amount, expense_type FROM expenses WHERE category = ? COLLATE NOCASE", (category,)
            ).fetchone()
            final_amount = amount + float(existing["amount"]) if existing and add else amount
            connection.execute(
                """
                INSERT INTO expenses(category, amount, expense_type, updated_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(category) DO UPDATE SET
                    amount = excluded.amount,
                    expense_type = excluded.expense_type,
                    updated_at = excluded.updated_at
                """,
                (category, final_amount, expense_type, self._now()),
            )
        self.log_change(
            "gasto_atualizado" if existing else "gasto_adicionado",
            {
                "categoria": category,
                "valor_anterior": float(existing["amount"]) if existing else None,
                "valor_atual": final_amount,
                "tipo": expense_type,
                "origem": source,
            },
        )

    def remove_expense(self, category: str, source: str = "chat") -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT category, amount, expense_type FROM expenses WHERE category = ? COLLATE NOCASE",
                (category.strip(),),
            ).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM expenses WHERE category = ? COLLATE NOCASE", (category.strip(),))
        self.log_change("gasto_removido", {**dict(row), "origem": source})
        return True

    def list_limits(self) -> dict[str, float]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT category, amount FROM category_limits ORDER BY category COLLATE NOCASE"
            ).fetchall()
        return {normalize(row["category"]): float(row["amount"]) for row in rows}

    def upsert_limit(self, category: str, amount: float, source: str = "chat") -> None:
        category = category.strip()[:40]
        if not category:
            raise ValueError("A categoria é obrigatória")
        amount = float(amount)
        if amount <= 0:
            raise ValueError("O limite precisa ser maior que zero")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT amount FROM category_limits WHERE category = ? COLLATE NOCASE",
                (category,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO category_limits(category, amount, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(category) DO UPDATE SET
                    amount = excluded.amount,
                    updated_at = excluded.updated_at
                """,
                (category, amount, self._now()),
            )
        self.log_change(
            "limite_atualizado" if existing else "limite_adicionado",
            {
                "categoria": category,
                "valor_anterior": float(existing["amount"]) if existing else None,
                "valor_atual": amount,
                "origem": source,
            },
        )

    def remove_limit(self, category: str, source: str = "chat") -> bool:
        category = category.strip()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT category, amount FROM category_limits WHERE category = ? COLLATE NOCASE",
                (category,),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "DELETE FROM category_limits WHERE category = ? COLLATE NOCASE",
                (category,),
            )
        self.log_change("limite_removido", {**dict(row), "origem": source})
        return True

    def replace_expenses(self, rows: list[dict[str, Any]], source: str = "editor") -> None:
        clean_rows = []
        seen = set()
        for row in rows:
            category = str(row.get("Categoria", "")).strip()[:40]
            if not category or normalize(category) in seen:
                continue
            seen.add(normalize(category))
            amount = max(0.0, float(row.get("Valor mensal", 0)))
            expense_type = str(row.get("Tipo", "Variável"))
            if expense_type not in {"Fixa", "Variável", "Planejamento"}:
                expense_type = "Variável"
            clean_rows.append((category, amount, expense_type, self._now()))

        previous = self.list_expenses()
        comparable_previous = [
            (row["category"], round(float(row["amount"]), 2), row["expense_type"]) for row in previous
        ]
        comparable_new = [(row[0], round(row[1], 2), row[2]) for row in clean_rows]
        if comparable_previous == comparable_new:
            return

        with self._connect() as connection:
            connection.execute("DELETE FROM expenses")
            connection.executemany(
                "INSERT INTO expenses(category, amount, expense_type, updated_at) VALUES (?, ?, ?, ?)",
                clean_rows,
            )
        self.log_change("orcamento_editado", {"categorias": len(clean_rows), "origem": source})

    def add_goal(self, name: str, target: float, current: float, deadline: str, source: str = "interface") -> int:
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO goals(name, target, current, deadline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name.strip()[:60], float(target), max(0.0, float(current)), deadline, now, now),
            )
            goal_id = cursor.lastrowid
            if goal_id is None:
                raise RuntimeError("Não foi possível obter o ID da meta criada.")
        self.log_change("meta_adicionada", {"id": goal_id, "nome": name, "origem": source})
        return goal_id

    def list_goals(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, target, current, deadline FROM goals ORDER BY created_at, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def remove_goal(self, goal_id: int, source: str = "interface") -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        self.log_change("meta_removida", {"id": goal_id, "nome": row["name"], "origem": source})
        return True

    def add_goal_contribution(self, goal_name: str, amount: float, source: str = "chat") -> dict | None:
        goals = self.list_goals()
        target_name = normalize(goal_name)
        matches = [goal for goal in goals if target_name in normalize(goal["name"]) or normalize(goal["name"]) in target_name]
        if len(matches) != 1:
            return None
        goal = matches[0]
        new_current = min(float(goal["target"]), float(goal["current"]) + max(0.0, float(amount)))
        with self._connect() as connection:
            connection.execute(
                "UPDATE goals SET current = ?, updated_at = ? WHERE id = ?",
                (new_current, self._now(), goal["id"]),
            )
        self.log_change(
            "aporte_registrado",
            {"meta": goal["name"], "valor": amount, "total_atual": new_current, "origem": source},
        )
        return {**goal, "current": new_current}

    def save_message(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"} or not content.strip():
            return
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO chat_history(role, content, created_at) VALUES (?, ?, ?)",
                (role, content.strip(), self._now()),
            )

    def list_messages(self, limit: int = 80) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content FROM chat_history ORDER BY id DESC LIMIT ?
                ) ORDER BY id
                """,
                (limit,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def clear_chat(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM chat_history")
        self.log_change("historico_chat_limpo", {"origem": "interface"})

    def log_change(self, action: str, details: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO change_log(action, details, created_at) VALUES (?, ?, ?)",
                (action, json.dumps(details, ensure_ascii=False), self._now()),
            )

    def list_changes(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT action, details, created_at FROM change_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {
                "action": row["action"],
                "details": json.loads(row["details"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
