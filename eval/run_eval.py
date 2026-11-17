"""Answer-correctness evaluation against the real local model.

    cd backend && .venv/bin/python ../eval/run_eval.py

For each case the generated SQL is executed (read-only) and its *result* is
compared with the result of a hand-written reference query. Passing validation
or executing without error does not count as correct.

Scoring
- Rows are compared as multisets (as lists when order_matters is true).
  Floats are rounded to 2 decimals.
- Extra columns are tolerated: a case passes if some subset/ordering of the
  generated columns equals the reference columns.
- Ambiguous cases list several reference queries; matching any one passes.
- Unanswerable cases pass only if the model replies CANNOT_ANSWER.
"""
import asyncio
import json
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.readonly import execute_readonly  # noqa: E402
from app.services.sql_agent_service import SQLAgentService  # noqa: E402
from app.utils.schema_extractor import extract_schema  # noqa: E402

DB = str(ROOT / "samples" / "shop.db")


def _norm(v):
    if isinstance(v, float):
        v = round(v, 2)
        return int(v) if v.is_integer() else v
    return v


def _rows(rows):
    return [tuple(_norm(v) for v in r) for r in rows]


def results_match(gen_rows, ref_rows, order_matters=False):
    gen, ref = _rows(gen_rows), _rows(ref_rows)
    if len(gen) != len(ref):
        return False
    if not ref:
        return True
    k, n = len(ref[0]), len(gen[0]) if gen else 0
    if n < k:
        return False
    key = (lambda x: x) if order_matters else (lambda x: sorted(x, key=repr))
    target = key(ref)
    for cols in permutations(range(n), k):
        if key([tuple(r[i] for i in cols) for r in gen]) == target:
            return True
    return False


def score(case, gen, rows, err):
    if case.get("expect_cannot_answer"):
        return bool(gen.cannot_answer), "refused" if gen.cannot_answer else "answered an unanswerable question"
    if gen.cannot_answer:
        return False, f"refused: {gen.cannot_answer}"
    if not gen.is_valid:
        return False, "invalid SQL: " + "; ".join(e.message for e in gen.validation_errors)
    if err:
        return False, f"execution error: {err}"
    for i, ref in enumerate(case["reference_sql"]):
        ref_rows = execute_readonly(DB, ref, max_rows=1000).rows
        if results_match(rows, ref_rows, case.get("order_matters", False)):
            return True, f"matches reference {i + 1}" if len(case["reference_sql"]) > 1 else "matches reference"
    return False, "wrong result"


async def main():
    cases = json.loads((ROOT / "eval" / "cases.json").read_text())
    agent = SQLAgentService()
    schema = extract_schema(DB, name="shop")
    # Warm-up so model load time is not counted as query latency.
    await agent.generate_sql("How many customers are there?", schema)
    out = []
    for c in cases:
        gen = await agent.generate_sql(c["question"], schema)
        rows, err = None, None
        if gen.is_valid:
            try:
                rows = execute_readonly(DB, gen.sql, max_rows=1000).rows
            except Exception as e:
                err = str(e)
        ok, why = score(c, gen, rows, err)
        out.append({"id": c["id"], "category": c["category"], "question": c["question"], "correct": ok,
                    "reason": why, "sql": gen.sql, "assumption": gen.assumption,
                    "cannot_answer": gen.cannot_answer, "latency_ms": gen.generation_time_ms})
        print(f"{'PASS' if ok else 'FAIL'}  {c['id']:9} {gen.generation_time_ms:7.0f} ms  {why}")
    write_report(out, agent.model)


def write_report(out, model):
    lat = sorted(r["latency_ms"] for r in out)
    p95 = lat[min(len(lat) - 1, round(0.95 * (len(lat) - 1)))]
    passed = sum(r["correct"] for r in out)
    try:
        ollama_v = subprocess.run(["ollama", "--version"], capture_output=True, text=True).stdout.strip().splitlines()[-1]
    except Exception:
        ollama_v = "unknown"
    meta = {"model": model, "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "machine": platform.machine(),
            "ollama": ollama_v, "passed": passed, "total": len(out),
            "median_latency_ms": round(statistics.median(lat)), "p95_latency_ms": round(p95)}
    (ROOT / "eval" / "results.json").write_text(json.dumps({"meta": meta, "results": out}, indent=2) + "\n")

    cats = {}
    for r in out:
        cats.setdefault(r["category"], []).append(r["correct"])
    amb = [r for r in out if r["category"] == "ambiguous"]
    meta["ambiguous_with_stated_assumption"] = sum(bool(r["assumption"]) for r in amb)
    (ROOT / "eval" / "results.json").write_text(json.dumps({"meta": meta, "results": out}, indent=2) + "\n")
    lines = [
        "# QueryForge evaluation results", "",
        f"- Model: `{model}` via Ollama ({ollama_v}), temperature 0, seed 0",
        f"- Date: {meta['date']}, machine: {platform.system()} {meta['machine']}",
        f"- Dataset: `samples/shop.db` (synthetic), cases: `eval/cases.json`",
        f"- **Answer correctness: {passed}/{len(out)}** (result compared with a reference query's result, not just SQL validity)",
        f"- Generation latency (warm model): median {meta['median_latency_ms']} ms, p95 {meta['p95_latency_ms']} ms",
        f"- Ambiguous questions where the model stated its assumption: {meta['ambiguous_with_stated_assumption']}/{len(amb)}", "",
        "| Category | Correct |", "|---|---|",
        *[f"| {k} | {sum(v)}/{len(v)} |" for k, v in cats.items()], "",
        "| Case | Question | Result | Why | Generated SQL |", "|---|---|---|---|---|",
    ]
    for r in out:
        sql = (r["sql"] or f"CANNOT_ANSWER: {r['cannot_answer']}").replace("\n", " ").replace("|", "\\|")
        why = r["reason"] + (f" (assumption stated: {r['assumption']})" if r["assumption"] else "")
        lines.append(f"| {r['id']} | {r['question']} | {'✅' if r['correct'] else '❌'} | {why.replace('|', '/')} | `{sql}` |")
    lines += [
        "", "## How a case is scored", "",
        "- The generated SQL is run read-only and its rows are compared with the rows of a hand-written reference query.",
        "- Rows are compared as multisets (in order when the case sets `order_matters`). Floats are rounded to 2 decimals.",
        "- Extra columns are allowed: the case passes if some choice and order of the generated columns equals the reference columns.",
        "- Ambiguous cases list every accepted reading; matching any one passes. Whether the model *stated* its assumption is reported separately above.",
        "- Unanswerable cases pass only if the model replies `CANNOT_ANSWER`. SQL that runs and returns nothing counts as a failure.",
        "- Invalid SQL, execution errors and refusals of answerable questions all count as failures.",
        "- The scorer itself is tested against realistic wrong queries in `backend/tests/test_eval_scoring.py`.",
        "",
        "## Limits",
        "",
        "16 hand-written questions on one small synthetic schema, written by the same person who wrote the prompt. "
        "Result comparison only catches mistakes that change the result on *this* data. "
        "This shows how the demo behaves; it is not a benchmark and says nothing about other databases.",
        "",
    ]
    (ROOT / "eval" / "results.md").write_text("\n".join(lines))
    print(f"\n{passed}/{len(out)} correct; median {meta['median_latency_ms']} ms; p95 {meta['p95_latency_ms']} ms")


if __name__ == "__main__":
    asyncio.run(main())
