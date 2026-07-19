import json
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from tools.postgres.posgresql_exec import _validate_sql, execute_sql_safe


class ValidateSQLTests(unittest.TestCase):
    def test_accepts_parameterized_select(self) -> None:
        statement = _validate_sql(
            "SELECT id, name FROM customers WHERE id = :customer_id",
            {"customer_id": 10},
        )

        self.assertEqual(statement.key, "select")

    def test_accepts_schema_discovery_for_allowed_table(self) -> None:
        statement = _validate_sql(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = :table_name ORDER BY ordinal_position",
            {"table_name": "customers"},
        )

        self.assertEqual(statement.key, "select")

    def test_rejects_schema_discovery_for_unallowed_table(self) -> None:
        with self.assertRaisesRegex(ValueError, "table_name parametrizado"):
            _validate_sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table_name",
                {"table_name": "users"},
            )

    def test_rejects_unfiltered_schema_discovery(self) -> None:
        with self.assertRaisesRegex(ValueError, "filtrar uma única tabela"):
            _validate_sql("SELECT column_name FROM information_schema.columns", {})

    def test_accepts_parameterized_update(self) -> None:
        statement = _validate_sql(
            "UPDATE customers SET name = :name WHERE id = :customer_id",
            {"name": "Ana", "customer_id": 10},
        )

        self.assertEqual(statement.key, "update")

    def test_rejects_select_without_allowed_table(self) -> None:
        with self.assertRaisesRegex(ValueError, "pelo menos uma tabela"):
            _validate_sql("SELECT 1", {})

    def test_rejects_dangerous_select_function(self) -> None:
        with self.assertRaisesRegex(ValueError, "PG_READ_FILE"):
            _validate_sql(
                "SELECT pg_read_file(:path) FROM customers",
                {"path": "/etc/passwd"},
            )

    def test_rejects_table_outside_allowlist(self) -> None:
        with self.assertRaisesRegex(ValueError, "Tabelas não permitidas"):
            _validate_sql("DELETE FROM audit_log WHERE id = :id", {"id": 1})

    def test_rejects_schema_qualified_table(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema ou catálogo"):
            _validate_sql("DELETE FROM private.customers WHERE id = :id", {"id": 1})

    def test_rejects_update_without_where(self) -> None:
        with self.assertRaisesRegex(ValueError, "possuir WHERE"):
            _validate_sql("UPDATE customers SET name = :name", {"name": "Ana"})

    def test_rejects_literal_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "enviados em params"):
            _validate_sql("UPDATE customers SET name = 'Ana' WHERE id = :id", {"id": 1})

    def test_rejects_mismatched_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "não correspondem"):
            _validate_sql(
                "DELETE FROM orders WHERE customer_id = :customer_id",
                {"wrong_name": 1},
            )


class ExecuteSQLSafeTests(unittest.TestCase):
    @patch("tools.postgres.posgresql_exec._get_engine")
    @patch("tools.postgres.posgresql_exec.load_llm")
    @patch("tools.postgres.posgresql_exec.interrupt")
    def test_select_returns_rows_without_confirmation(
        self,
        interrupt_mock: MagicMock,
        load_llm_mock: MagicMock,
        get_engine_mock: MagicMock,
    ) -> None:
        result_mock = MagicMock()
        result_mock.mappings.return_value.fetchmany.return_value = [
            {"id": 10, "name": "Ana"}
        ]
        connection_mock = MagicMock()
        connection_mock.execute.return_value = result_mock
        get_engine_mock.return_value.connect.return_value.__enter__.return_value = (
            connection_mock
        )

        result = execute_sql_safe.func(
            "SELECT id, name FROM customers WHERE id = :customer_id",
            {"customer_id": 10},
        )

        self.assertEqual(
            json.loads(result),
            {
                "rows": [{"id": 10, "name": "Ana"}],
                "returned_rows": 1,
                "truncated": False,
            },
        )
        interrupt_mock.assert_not_called()
        load_llm_mock.assert_not_called()

    @patch("tools.postgres.posgresql_exec._get_engine")
    def test_accepts_json_string_params_with_redundant_closing_brace(
        self, get_engine_mock: MagicMock
    ) -> None:
        result_mock = MagicMock()
        result_mock.mappings.return_value.fetchmany.return_value = [
            {"column_name": "name"}
        ]
        connection_mock = MagicMock()
        connection_mock.execute.return_value = result_mock
        get_engine_mock.return_value.connect.return_value.__enter__.return_value = (
            connection_mock
        )

        result = execute_sql_safe.invoke(
            {
                "query": (
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :table_name"
                ),
                "params": '{"table_name":"customers"}\n}',
            }
        )

        self.assertEqual(json.loads(result)["rows"], [{"column_name": "name"}])
        executed_params = connection_mock.execute.call_args.args[1]
        self.assertEqual(executed_params, {"table_name": "customers"})

    @patch("tools.postgres.posgresql_exec._get_engine")
    @patch("tools.postgres.posgresql_exec.load_llm")
    @patch("tools.postgres.posgresql_exec.interrupt", return_value="sim, pode executar")
    def test_executes_only_after_approval(
        self,
        interrupt_mock: MagicMock,
        load_llm_mock: MagicMock,
        get_engine_mock: MagicMock,
    ) -> None:
        load_llm_mock.return_value.invoke.return_value = AIMessage(content="1")
        result_mock = MagicMock(rowcount=2)
        connection_mock = MagicMock()
        connection_mock.execute.return_value = result_mock
        get_engine_mock.return_value.begin.return_value.__enter__.return_value = (
            connection_mock
        )

        result = execute_sql_safe.func(
            "DELETE FROM orders WHERE customer_id = :customer_id",
            {"customer_id": 10},
        )

        self.assertEqual(result, "Operação executada com sucesso. Linhas afetadas: 2.")
        interrupt_mock.assert_called_once()
        load_llm_mock.assert_called_once_with()
        connection_mock.execute.assert_called_once()

    @patch("tools.postgres.posgresql_exec._get_engine")
    @patch("tools.postgres.posgresql_exec.load_llm")
    @patch("tools.postgres.posgresql_exec.interrupt", return_value="não")
    def test_does_not_connect_when_user_rejects(
        self,
        _interrupt_mock: MagicMock,
        load_llm_mock: MagicMock,
        get_engine_mock: MagicMock,
    ) -> None:
        load_llm_mock.return_value.invoke.return_value = AIMessage(content="2")
        result = execute_sql_safe.func(
            "DELETE FROM orders WHERE customer_id = :customer_id",
            {"customer_id": 10},
        )

        self.assertEqual(result, "Operação cancelada pelo usuário.")
        get_engine_mock.assert_not_called()

    @patch("tools.postgres.posgresql_exec._get_engine")
    @patch("tools.postgres.posgresql_exec.load_llm")
    @patch("tools.postgres.posgresql_exec.interrupt", return_value="talvez")
    def test_treats_unexpected_model_output_as_rejection(
        self,
        _interrupt_mock: MagicMock,
        load_llm_mock: MagicMock,
        get_engine_mock: MagicMock,
    ) -> None:
        load_llm_mock.return_value.invoke.return_value = AIMessage(content="positivo")

        result = execute_sql_safe.func(
            "DELETE FROM orders WHERE customer_id = :customer_id",
            {"customer_id": 10},
        )

        self.assertEqual(result, "Operação cancelada pelo usuário.")
        get_engine_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
