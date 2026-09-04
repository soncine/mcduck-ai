import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat_actions import process_command  # noqa: E402
from database import FinanceDatabase  # noqa: E402


class PersistenceAndActionsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = FinanceDatabase(self.db_path)
        self.db.seed_defaults(5000, {"Moradia": 1200, "Alimentação": 600})

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_data_survives_new_database_instance(self):
        self.db.set_income(6500)
        self.db.upsert_expense("Pets", 250, "Variável")
        self.db.upsert_limit("Pets", 300)
        self.db.add_goal("Viagem", 6000, 1000, "2027-12")
        self.db.save_message("user", "Mensagem persistida")

        reopened = FinanceDatabase(self.db_path)
        self.assertEqual(reopened.get_income(), 6500)
        self.assertTrue(any(item["category"] == "Pets" for item in reopened.list_expenses()))
        self.assertEqual(reopened.list_limits()["pets"], 300)
        self.assertEqual(reopened.list_goals()[0]["name"], "Viagem")
        self.assertEqual(reopened.list_messages()[0]["content"], "Mensagem persistida")

    def test_chat_can_add_expense_category(self):
        result = process_command("Adicione R$ 300 em Pets", self.db, available=3200)
        pets = next(item for item in self.db.list_expenses() if item["category"] == "Pets")
        self.assertTrue(result.changed)
        self.assertEqual(pets["amount"], 300)

    def test_chat_can_create_update_and_remove_category_limit(self):
        created = process_command(
            "Defina o limite de Alimentação em R$ 700",
            self.db,
            available=3200,
        )
        updated = process_command(
            "Altere o limite de Alimentação para R$ 650",
            self.db,
            available=3200,
        )

        self.assertTrue(created.changed)
        self.assertTrue(updated.changed)
        self.assertEqual(self.db.list_limits()["alimentacao"], 650)

        removed = process_command(
            "Remova o limite de Alimentação",
            self.db,
            available=3200,
        )
        self.assertTrue(removed.changed)
        self.assertNotIn("alimentacao", self.db.list_limits())

    def test_chat_accepts_limit_value_before_category(self):
        result = process_command(
            "Coloque um limite de 300 em Lazer",
            self.db,
            available=3200,
        )
        self.assertTrue(result.changed)
        self.assertEqual(self.db.list_limits()["lazer"], 300)

    def test_incomplete_limit_command_asks_for_missing_value(self):
        result = process_command(
            "Defina um limite para Alimentação",
            self.db,
            available=3200,
        )
        self.assertTrue(result.handled)
        self.assertFalse(result.changed)
        self.assertIn("qual valor", result.message.lower())

    def test_investment_is_allowed_as_budget_category(self):
        result = process_command(
            "Gostaria de colocar todo o dinheiro que sobra em investimento",
            self.db,
            available=3200,
        )
        investment = next(
            item for item in self.db.list_expenses() if item["category"] == "Investimentos"
        )
        self.assertTrue(result.changed)
        self.assertEqual(investment["amount"], 3200)
        self.assertEqual(investment["expense_type"], "Planejamento")

    def test_investment_education_is_refused(self):
        before = self.db.list_expenses()
        result = process_command("Me ensine como funciona um CDB", self.db, available=3200)
        self.assertTrue(result.handled)
        self.assertIn("não ensino", result.message.lower())
        self.assertEqual(self.db.list_expenses(), before)

    def test_chat_reorganizes_new_income_preserving_existing_expenses(self):
        result = process_command(
            "Comecei a receber R$ 6.000 e gostaria de dividir tudo da melhor forma possível",
            self.db,
            available=3200,
        )
        expenses = self.db.list_expenses()
        total = sum(item["amount"] for item in expenses)
        planning = [item for item in expenses if item["expense_type"] == "Planejamento"]
        self.assertTrue(result.changed)
        self.assertTrue(result.income_changed)
        self.assertEqual(self.db.get_income(), 6000)
        self.assertAlmostEqual(total, 6000)
        self.assertEqual(len(planning), 3)

    def test_unformatted_income_is_parsed_completely(self):
        result = process_command(
            "Minha renda passou para 6000",
            self.db,
            available=3200,
        )
        self.assertTrue(result.income_changed)
        self.assertEqual(self.db.get_income(), 6000)

    def test_chat_creates_goal_and_registers_contribution(self):
        created = process_command(
            "Crie a meta Viagem de R$ 6.000 para 12/2027",
            self.db,
            available=3200,
        )
        contribution = process_command(
            "Registre um aporte de R$ 500 na meta Viagem",
            self.db,
            available=3200,
        )
        goal = self.db.list_goals()[0]
        self.assertTrue(created.changed)
        self.assertTrue(contribution.changed)
        self.assertEqual(goal["name"], "Viagem")
        self.assertEqual(goal["current"], 500)

    def test_goal_without_value_asks_for_missing_information(self):
        result = process_command(
            "Crie a meta Viagem para 12/2027",
            self.db,
            available=3200,
        )
        self.assertFalse(result.changed)
        self.assertIn("informe o nome, o valor desejado e o prazo", result.message.lower())
        self.assertEqual(self.db.list_goals(), [])


if __name__ == "__main__":
    unittest.main()
