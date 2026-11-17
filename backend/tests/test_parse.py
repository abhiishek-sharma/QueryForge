from app.services.sql_agent_service import parse_model_output


def test_fenced_sql():
    assert parse_model_output("```sql\nSELECT 1;\n```")[0] == "SELECT 1;"


def test_keeps_with_clause():
    sql, _, _ = parse_model_output("```sql\nWITH t AS (\nSELECT 1 AS x)\nSELECT x FROM t\n```")
    assert sql.startswith("WITH t AS")


def test_assumption_extracted():
    sql, assumption, _ = parse_model_output("```sql\n-- Assumption: only completed orders\nSELECT 1\n```")
    assert assumption == "only completed orders"
    assert sql == "SELECT 1"


def test_cannot_answer():
    sql, _, reason = parse_model_output("CANNOT_ANSWER: there is no email column")
    assert sql == "" and reason == "there is no email column"


def test_prose_before_block():
    assert parse_model_output("Sure:\n```sql\nSELECT 2\n```\nHope this helps")[0] == "SELECT 2"


def test_second_statement_not_silently_dropped():
    # The validator must see (and reject) the second statement.
    assert "DROP" in parse_model_output("SELECT 1; DROP TABLE t")[0]
