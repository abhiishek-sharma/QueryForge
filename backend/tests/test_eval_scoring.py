"""The eval scorer must not pass wrong answers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
from run_eval import results_match  # noqa: E402


def test_same_rows_any_order():
    assert results_match([("b", 2), ("a", 1)], [("a", 1), ("b", 2)])


def test_order_enforced_when_required():
    assert not results_match([("b", 2), ("a", 1)], [("a", 1), ("b", 2)], order_matters=True)


def test_extra_columns_tolerated_and_reordered():
    assert results_match([(1, "a", 9.999), (2, "b", 1.0)], [(10.0, "a"), (1.0, "b")])


def test_wrong_values_fail():
    assert not results_match([("a", 1)], [("a", 2)])


def test_wrong_row_count_fails():
    assert not results_match([("a",), ("b",)], [("a",)])


def test_missing_column_fails():
    assert not results_match([("a",)], [("a", 1)])


def test_float_rounding():
    assert results_match([(0.1 + 0.2,)], [(0.3,)])


# --- score() against the real sample DB with realistic wrong SQL -------------
import json  # noqa: E402

import pytest  # noqa: E402

from app.db.readonly import execute_readonly  # noqa: E402
from app.schemas.sql_schemas import GenerationResult  # noqa: E402
from app.utils.sql_safety import validate  # noqa: E402
from run_eval import DB, ROOT, score  # noqa: E402

CASES = {c["id"]: c for c in json.loads((ROOT / "eval" / "cases.json").read_text())}


def _score(case_id, sql=None, cannot=None):
    if cannot:
        return score(CASES[case_id], GenerationResult(cannot_answer=cannot), None, None)[0]
    ok, errs = validate(sql)
    rows, err = None, None
    try:
        rows = execute_readonly(DB, sql, max_rows=1000).rows
    except Exception as e:
        err = str(e)
    return score(CASES[case_id], GenerationResult(sql=sql, is_valid=ok, validation_errors=errs), rows, err)[0]


@pytest.mark.parametrize("case_id,sql", [
    # aggregation without GROUP BY: one row instead of one per category
    ("agg-1", "SELECT category, count(*) FROM products"),
    # wrong filter: counts every order instead of only cancelled ones
    ("filter-3", "SELECT count(*) FROM orders"),
    # ">=" instead of ">" (a product costs exactly 100)
    ("filter-2", "SELECT name FROM products WHERE price >= 100"),
    # off-by-one comparison on a date range (misses 31 March)
    ("filter-4", "SELECT name FROM customers WHERE signup_date >= '2024-03-01' AND signup_date < '2024-03-31'"),
    # join written as a cross join: rows explode
    ("join-1", "SELECT p.category, sum(oi.quantity * oi.unit_price) FROM order_items oi, orders o, products p WHERE o.status = 'completed' GROUP BY p.category"),
    # forgets the completed-orders filter
    ("join-2", "SELECT c.name, sum(oi.quantity * oi.unit_price) AS s FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id GROUP BY c.id ORDER BY s DESC LIMIT 3"),
    # right rows, wrong order, when order matters
    ("join-2", "SELECT c.name, sum(oi.quantity * oi.unit_price) AS s FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id WHERE o.status = 'completed' GROUP BY c.id ORDER BY s ASC LIMIT 3"),
    # answers the ambiguous question with a reading that is not listed (average instead of total)
    ("ambig-1", "SELECT avg(quantity * unit_price) FROM order_items"),
    # an unanswerable question answered with SQL that runs and returns nothing
    ("unans-1", "SELECT name FROM customers WHERE 0"),
    # hallucinated column
    ("unans-1", "SELECT email FROM customers"),
])
def test_wrong_answers_fail(case_id, sql):
    assert _score(case_id, sql) is False


def test_refusing_an_answerable_question_fails():
    assert _score("filter-1", cannot="no data") is False


def test_reference_sql_scores_as_correct():
    for cid, c in CASES.items():
        if "reference_sql" in c:
            assert _score(cid, c["reference_sql"][0]) is True, cid
    assert _score("unans-1", cannot="no email column") is True
