from tools.postgres.posgresql_exec import execute_sql_safe


def get_postgres_tools():
    """Returns a list of PostgreSQL tools."""
    return [
        execute_sql_safe,
    ]
