from app.utils.sql_safety import SQLSafetyValidator


class TestSQLSafetyValidator:

    def test_valid_select(self):
        is_valid, errors = SQLSafetyValidator.validate("SELECT * FROM users", strict_mode=True)
        assert is_valid
        assert len([e for e in errors if e.severity in ("error", "critical")]) == 0

    def test_blocks_drop_table(self):
        is_valid, errors = SQLSafetyValidator.validate("DROP TABLE users", strict_mode=True)
        assert not is_valid
        types = {e.error_type for e in errors}
        assert "dangerous_operation" in types or "forbidden_operation" in types

    def test_blocks_delete_from(self):
        is_valid, errors = SQLSafetyValidator.validate("DELETE FROM users", strict_mode=True)
        assert not is_valid

    def test_blocks_update(self):
        is_valid, errors = SQLSafetyValidator.validate("UPDATE users SET name='x'", strict_mode=True)
        assert not is_valid

    def test_blocks_sql_injection_semicolon(self):
        is_valid, errors = SQLSafetyValidator.validate(
            "SELECT 1; DROP TABLE users", strict_mode=True
        )
        assert not is_valid
        types = {e.error_type for e in errors}
        assert "dangerous_operation" in types or "multiple_statements" in types

    def test_blocks_comment_injection(self):
        is_valid, errors = SQLSafetyValidator.validate(
            "SELECT * FROM users -- WHERE admin=1", strict_mode=True
        )
        assert not is_valid

    def test_blocks_truncate(self):
        is_valid, errors = SQLSafetyValidator.validate("TRUNCATE TABLE users", strict_mode=True)
        assert not is_valid

    def test_blocks_alter_table(self):
        is_valid, errors = SQLSafetyValidator.validate("ALTER TABLE users ADD col TEXT", strict_mode=True)
        assert not is_valid

    def test_blocks_insert(self):
        is_valid, errors = SQLSafetyValidator.validate(
            "INSERT INTO users VALUES (1, 'a')", strict_mode=True
        )
        assert not is_valid

    def test_empty_query(self):
        is_valid, errors = SQLSafetyValidator.validate("", strict_mode=True)
        assert not is_valid

    def test_sanitize_adds_limit(self):
        result = SQLSafetyValidator.sanitize_sql("SELECT * FROM users", max_rows=50)
        assert "LIMIT 50" in result

    def test_sanitize_keeps_existing_limit(self):
        result = SQLSafetyValidator.sanitize_sql("SELECT * FROM users LIMIT 10", max_rows=50)
        assert "LIMIT 10" in result
        assert "LIMIT 50" not in result

    def test_format_sql(self):
        result = SQLSafetyValidator.format_sql("select id, name from users where id=1")
        assert "SELECT" in result
