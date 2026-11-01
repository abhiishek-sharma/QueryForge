import React, { useState, useRef } from "react";
import { api } from "./api";
import {
  Database,
  Upload,
  Send,
  AlertTriangle,
  CheckCircle,
  Copy,
  Check,
  FileSpreadsheet,
  Table2,
  X,
  Loader2,
} from "lucide-react";

function App() {
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const handleFileSelect = (e) => {
    const f = e.target.files[0];
    if (f) setFile(f);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.query(file, question.trim());
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async (text) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const clearFile = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const acceptedTypes = ".db,.sqlite,.sqlite3,.csv,.xlsx,.xls";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center">
            <Database size={18} className="text-white" />
          </div>
          <span className="font-semibold text-lg">QueryForge</span>
          <span className="text-sm text-slate-500 hidden sm:inline">
            Natural-language to SQL
          </span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Upload Section */}
        <section>
          <h2 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2">
            <Upload size={16} /> 1. Upload your data file
          </h2>
          {file ? (
            <div className="flex items-center gap-3 p-4 bg-slate-900 border border-slate-700 rounded-xl">
              <FileSpreadsheet size={24} className="text-emerald-400" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{file.name}</p>
                <p className="text-xs text-slate-500">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
              <button
                onClick={clearFile}
                className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              >
                <X size={18} />
              </button>
            </div>
          ) : (
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`cursor-pointer border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                dragOver
                  ? "border-emerald-500 bg-emerald-500/5"
                  : "border-slate-700 hover:border-slate-600"
              }`}
            >
              <Upload
                size={32}
                className="mx-auto mb-3 text-slate-500"
              />
              <p className="text-sm text-slate-400">
                Drag & drop or{" "}
                <span className="text-emerald-400 underline">browse</span>
              </p>
              <p className="text-xs text-slate-600 mt-1">
                SQLite (.db) &middot; CSV &middot; Excel (.xlsx)
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept={acceptedTypes}
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>
          )}
        </section>

        {/* Question Section */}
        <section>
          <h2 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2">
            <Send size={16} /> 2. Ask a question
          </h2>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Show the top 5 customers by total spend"
              className="flex-1 px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-sm focus:outline-none focus:border-emerald-500 placeholder-slate-600"
            />
            <button
              type="submit"
              disabled={!file || !question.trim() || loading}
              className="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
            >
              {loading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Send size={18} />
              )}
              Run
            </button>
          </form>
        </section>

        {/* Error */}
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start gap-3">
            <AlertTriangle size={20} className="text-red-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Generated SQL */}
            <section className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
                <h3 className="text-sm font-medium flex items-center gap-2">
                  <Database size={16} className="text-emerald-400" />
                  Generated SQL
                </h3>
                <div className="flex items-center gap-2">
                  {result.is_valid ? (
                    <span className="flex items-center gap-1 text-xs text-emerald-400">
                      <CheckCircle size={14} /> Valid
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-red-400">
                      <AlertTriangle size={14} /> Invalid
                    </span>
                  )}
                  <button
                    onClick={() => handleCopy(result.sql)}
                    className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
                    title="Copy SQL"
                  >
                    {copied ? (
                      <Check size={14} className="text-emerald-400" />
                    ) : (
                      <Copy size={14} />
                    )}
                  </button>
                </div>
              </div>
              <pre className="p-4 text-sm font-mono text-emerald-300 overflow-x-auto whitespace-pre-wrap">
                {result.sql || "(no SQL generated)"}
              </pre>
              {result.explanation && (
                <p className="px-4 pb-3 text-xs text-slate-500">
                  {result.explanation}
                </p>
              )}
            </section>

            {/* Validation Errors */}
            {result.validation_errors && result.validation_errors.length > 0 && (
              <section className="bg-red-500/5 border border-red-500/20 rounded-xl p-4 space-y-2">
                <h3 className="text-sm font-medium text-red-400">
                  Validation Issues
                </h3>
                {result.validation_errors.map((err, i) => (
                  <p key={i} className="text-xs text-red-300">
                    <span className="uppercase font-semibold">{err.severity}:</span>{" "}
                    {err.message}
                  </p>
                ))}
              </section>
            )}

            {/* Execution Error */}
            {result.execution_error && (
              <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl">
                <p className="text-sm text-yellow-300">
                  <AlertTriangle size={14} className="inline mr-1" />
                  Execution error: {result.execution_error}
                </p>
              </div>
            )}

            {/* Result Table */}
            {result.result && (
              <section className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
                  <h3 className="text-sm font-medium flex items-center gap-2">
                    <Table2 size={16} className="text-teal-400" />
                    Results
                  </h3>
                  <span className="text-xs text-slate-500">
                    {result.result.row_count} row{result.result.row_count !== 1 ? "s" : ""}{" "}
                    &middot; {result.result.execution_time_ms.toFixed(1)} ms
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 bg-slate-800/50">
                        {result.result.columns.map((col, i) => (
                          <th
                            key={i}
                            className="px-4 py-2 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider"
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.result.rows.map((row, ri) => (
                        <tr
                          key={ri}
                          className="border-b border-slate-800/50 hover:bg-slate-800/30"
                        >
                          {row.map((cell, ci) => (
                            <td key={ci} className="px-4 py-2 text-slate-300 whitespace-nowrap">
                              {cell === null ? (
                                <span className="text-slate-600 italic">NULL</span>
                              ) : (
                                String(cell)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {result.result.rows.length === 0 && (
                        <tr>
                          <td
                            colSpan={result.result.columns.length}
                            className="px-4 py-6 text-center text-slate-500"
                          >
                            No rows returned
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* Schema Info */}
            {result.schema && (
              <details className="bg-slate-900 border border-slate-700 rounded-xl">
                <summary className="px-4 py-3 text-sm font-medium cursor-pointer text-slate-400 hover:text-slate-200">
                  Detected Schema ({result.schema.tables?.length || 0} tables)
                </summary>
                <div className="px-4 pb-4">
                  {result.schema.tables?.map((table, i) => (
                    <div key={i} className="mt-2">
                      <p className="text-xs font-mono text-emerald-400">{table.name}</p>
                      <div className="ml-4 mt-1 space-y-0.5">
                        {table.columns?.map((col, j) => (
                          <p key={j} className="text-xs text-slate-500">
                            {col.name}{" "}
                            <span className="text-slate-600">{col.type}</span>
                            {col.primary_key && (
                              <span className="text-yellow-500 ml-1">PK</span>
                            )}
                          </p>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        {/* Empty state */}
        {!result && !error && !loading && (
          <section className="mt-8 text-center text-slate-600 space-y-4">
            <Database size={48} className="mx-auto opacity-30" />
            <p className="text-lg">Upload a file and ask a question to get started</p>
            <p className="text-sm max-w-md mx-auto">
              QueryForge generates SQL from natural language, validates it for safety, and executes it on your data — all read-only.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
