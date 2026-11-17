import React, { useEffect, useRef, useState } from "react";
import { api } from "./api";
import {
  AlertTriangle, Check, CheckCircle, Copy, Database, FileSpreadsheet,
  HelpCircle, Info, Loader2, Send, Table2, Upload, X,
} from "lucide-react";

const ACCEPTED = ".db,.sqlite,.sqlite3,.csv,.xlsx";
const EXAMPLES = [
  "Which 3 customers spent the most on completed orders?",
  "How many orders were placed in each month of 2025?",
  "Which products cost more than 100?",
];

function HealthBadge({ health }) {
  if (!health) return <span className="text-xs text-slate-500">checking backend…</span>;
  if (health.error === "backend")
    return <span className="text-xs text-red-400">backend not reachable</span>;
  const ok = health.ollama_reachable && health.model_pulled;
  return (
    <span className={`text-xs flex items-center gap-1.5 ${ok ? "text-emerald-400" : "text-amber-400"}`}>
      <span className={`w-2 h-2 rounded-full ${ok ? "bg-emerald-400" : "bg-amber-400"}`} />
      {ok ? `${health.model} (local)` : !health.ollama_reachable ? "Ollama not running" : `run: ollama pull ${health.model}`}
    </span>
  );
}

function Panel({ icon: Icon, title, right, children, tone = "slate" }) {
  const border = { slate: "border-slate-700", red: "border-red-500/30", amber: "border-amber-500/30" }[tone];
  return (
    <section className={`bg-slate-900 border ${border} rounded-xl overflow-hidden`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 gap-2">
        <h3 className="text-sm font-medium flex items-center gap-2">
          <Icon size={16} className="text-emerald-400" /> {title}
        </h3>
        {right}
      </div>
      {children}
    </section>
  );
}

function ResultTable({ result }) {
  return (
    <Panel
      icon={Table2}
      title="Result"
      right={
        <span className="text-xs text-slate-500">
          {result.row_count} row{result.row_count !== 1 ? "s" : ""}
          {result.truncated ? " (truncated)" : ""} · {result.execution_time_ms.toFixed(1)} ms
        </span>
      }
    >
      <div className="overflow-x-auto max-h-[28rem]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-800">
            <tr>
              {result.columns.map((c, i) => (
                <th key={i} className="px-4 py-2 text-left text-xs font-semibold text-slate-300 whitespace-nowrap">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, ri) => (
              <tr key={ri} className="border-b border-slate-800/60 hover:bg-slate-800/40">
                {row.map((cell, ci) => (
                  <td key={ci} className={`px-4 py-2 whitespace-nowrap ${typeof cell === "number" ? "text-right tabular-nums" : ""}`}>
                    {cell === null ? <span className="text-slate-600 italic">NULL</span> : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
            {result.rows.length === 0 && (
              <tr><td colSpan={result.columns.length || 1} className="px-4 py-6 text-center text-slate-500">No rows returned</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {result.truncated && (
        <p className="px-4 py-2 text-xs text-amber-300 border-t border-slate-800">
          Only the first {result.row_count} rows are shown.
        </p>
      )}
    </Panel>
  );
}

function App() {
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [health, setHealth] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ error: "backend" }));
  }, []);

  const pick = (f) => { if (f) { setFile(f); setData(null); setError(null); } };

  const submit = async (e) => {
    e.preventDefault();
    if (!file || !question.trim() || loading) return;
    setLoading(true); setError(null); setData(null);
    try {
      setData(await api.query(file, question.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copy = async (text) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const gen = data?.generation;
  const blockingErrors = gen?.validation_errors?.filter((e) => e.error_type !== "llm_unavailable") || [];
  const llmDown = gen?.validation_errors?.find((e) => e.error_type === "llm_unavailable" || e.error_type === "generation_error");

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-3">
          <div className="w-8 h-8 bg-emerald-600 rounded-lg flex items-center justify-center">
            <Database size={18} className="text-white" />
          </div>
          <span className="font-semibold text-lg">QueryForge</span>
          <span className="text-sm text-slate-500 hidden sm:inline">Plain-English questions → read-only SQL</span>
          <span className="ml-auto"><HealthBadge health={health} /></span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <section>
          <h2 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2"><Upload size={16} /> 1. Upload a data file</h2>
          {file ? (
            <div className="flex items-center gap-3 p-4 bg-slate-900 border border-slate-700 rounded-xl">
              <FileSpreadsheet size={24} className="text-emerald-400" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{file.name}</p>
                <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
              <button aria-label="Remove file" onClick={() => { setFile(null); setData(null); if (inputRef.current) inputRef.current.value = ""; }}
                className="p-1.5 text-slate-400 hover:text-red-400 rounded-lg"><X size={18} /></button>
            </div>
          ) : (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); pick(e.dataTransfer.files[0]); }}
              onClick={() => inputRef.current?.click()}
              className={`cursor-pointer border-2 border-dashed rounded-xl p-8 text-center transition-colors ${dragOver ? "border-emerald-500 bg-emerald-500/5" : "border-slate-700 hover:border-slate-500"}`}
            >
              <Upload size={32} className="mx-auto mb-3 text-slate-500" />
              <p className="text-sm text-slate-300">Drag & drop or <span className="text-emerald-400 underline">browse</span></p>
              <p className="text-xs text-slate-500 mt-1">SQLite (.db, .sqlite) · CSV · Excel (.xlsx) · up to {health?.max_upload_mb ?? 25} MB</p>
              <p className="text-xs text-slate-500 mt-1">Try <code className="text-slate-400">samples/shop.db</code> from the repo</p>
              <input ref={inputRef} type="file" accept={ACCEPTED} onChange={(e) => pick(e.target.files[0])} className="hidden" />
            </div>
          )}
        </section>

        <section>
          <h2 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2"><Send size={16} /> 2. Ask a question</h2>
          <form onSubmit={submit} className="flex gap-2">
            <input
              type="text" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000}
              placeholder="e.g. Which 3 customers spent the most on completed orders?"
              className="flex-1 min-w-0 px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-sm focus:outline-none focus:border-emerald-500 placeholder-slate-600"
            />
            <button type="submit" disabled={!file || !question.trim() || loading}
              className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-xl text-sm font-medium flex items-center gap-2">
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />} Run
            </button>
          </form>
          <div className="flex flex-wrap gap-2 mt-2">
            {EXAMPLES.map((q) => (
              <button key={q} onClick={() => setQuestion(q)}
                className="text-xs px-2.5 py-1 rounded-full border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-500">{q}</button>
            ))}
          </div>
          {loading && <p className="text-xs text-slate-500 mt-2">Generating SQL with the local model. The first question after startup can take 30–60 s while the model loads.</p>}
        </section>

        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start gap-3">
            <AlertTriangle size={20} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {gen && (
          <div className="space-y-4">
            {llmDown && (
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-300 flex gap-3">
                <AlertTriangle size={18} className="shrink-0 mt-0.5" /> {llmDown.message}
              </div>
            )}

            {gen.cannot_answer && (
              <Panel icon={HelpCircle} title="The model could not answer this from the data" tone="amber">
                <p className="px-4 py-3 text-sm text-amber-200">{gen.cannot_answer}</p>
                <p className="px-4 pb-3 text-xs text-slate-500">No SQL was run. Rephrase the question, or check the detected schema below.</p>
              </Panel>
            )}

            {gen.sql && (
              <Panel
                icon={Database}
                title="Generated SQL"
                tone={gen.is_valid ? "slate" : "red"}
                right={
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">{gen.model} · {(gen.generation_time_ms / 1000).toFixed(1)} s</span>
                    <button onClick={() => copy(gen.sql)} title="Copy SQL" className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg">
                      {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                    </button>
                  </div>
                }
              >
                {gen.assumption && (
                  <p className="px-4 pt-3 text-xs text-sky-300 flex gap-2"><Info size={14} className="shrink-0" /> Assumption: {gen.assumption}</p>
                )}
                <pre className="p-4 text-sm font-mono text-emerald-300 overflow-x-auto whitespace-pre-wrap">{gen.sql}</pre>
                <div className="px-4 pb-3 text-xs text-slate-500 flex items-start gap-2">
                  {gen.is_valid && !data.execution_error ? (
                    <><CheckCircle size={14} className="text-emerald-500 shrink-0" />
                      Passed the read-only checks and ran. Check the SQL: running without errors does not mean it answers your question correctly.</>
                  ) : !gen.is_valid ? (
                    <><AlertTriangle size={14} className="text-red-400 shrink-0" /> Rejected before execution.</>
                  ) : null}
                </div>
              </Panel>
            )}

            {blockingErrors.length > 0 && (
              <section className="bg-red-500/5 border border-red-500/20 rounded-xl p-4 space-y-1">
                {blockingErrors.map((e, i) => <p key={i} className="text-xs text-red-300">{e.message}</p>)}
              </section>
            )}

            {data.execution_error && (
              <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl text-sm text-amber-200 flex gap-3">
                <AlertTriangle size={18} className="shrink-0 mt-0.5" /> {data.execution_error}
              </div>
            )}

            {data.result && <ResultTable result={data.result} />}

            <details className="bg-slate-900 border border-slate-700 rounded-xl">
              <summary className="px-4 py-3 text-sm cursor-pointer text-slate-400 hover:text-slate-200">
                Detected schema ({data.schema.tables.length} table{data.schema.tables.length !== 1 ? "s" : ""})
              </summary>
              <div className="px-4 pb-4 grid sm:grid-cols-2 gap-4">
                {data.schema.tables.map((t) => (
                  <div key={t.name}>
                    <p className="text-xs font-mono text-emerald-400">{t.name} <span className="text-slate-500">({t.row_count} rows)</span></p>
                    <ul className="ml-3 mt-1 space-y-0.5">
                      {t.columns.map((c) => (
                        <li key={c.name} className="text-xs text-slate-400 font-mono">
                          {c.name} <span className="text-slate-600">{c.type}</span>
                          {c.primary_key && <span className="text-amber-500 ml-1">PK</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}

        {!gen && !error && !loading && (
          <section className="mt-10 text-center text-slate-500 space-y-3">
            <Database size={44} className="mx-auto opacity-30" />
            <p>Upload a file and ask a question.</p>
            <p className="text-sm max-w-lg mx-auto">
              A local model writes one SQLite query, which then runs on a read-only copy of your file.
              Always check the SQL: a query can run and still answer a different question.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
