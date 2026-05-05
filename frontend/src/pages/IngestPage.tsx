import { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Trash2, Database, Files, Percent } from 'lucide-react';
import { getDocuments, uploadDocument, deleteDocument, getStats } from '../api/client';
import type { Document, Stats } from '../types';

// ── Pipeline step helper ─────────────────────────────────────────────────────

type StepState = 'wait' | 'running' | 'done' | 'error';

interface Step { label: string; state: StepState }

function getSteps(doc: Document): Step[] {
  const { status, progress } = doc;
  if (status === 'error') {
    return [
      { label: 'Parsing',  state: progress >= 15 ? 'done' : 'error' },
      { label: 'LLM Extract', state: progress >= 90 ? 'done' : progress >= 15 ? 'error' : 'wait' },
      { label: 'Indexing', state: 'wait' },
    ];
  }
  return [
    { label: 'Parsing',    state: status === 'done' || progress >= 15 ? 'done' : progress >= 5 ? 'running' : 'wait' },
    { label: 'LLM Extract',state: status === 'done' || progress >= 90 ? 'done' : progress >= 15 ? 'running' : 'wait' },
    { label: 'Indexing',   state: status === 'done' ? 'done' : progress >= 90 ? 'running' : 'wait' },
  ];
}

const stepIcon: Record<StepState, React.ReactNode> = {
  wait:    <span className="w-4 h-4 rounded-full border border-slate-300 dark:border-slate-600 inline-block" />,
  running: <Loader2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400 animate-spin" />,
  done:    <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />,
  error:   <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />,
};

const stepLabel: Record<StepState, string> = {
  wait: 'text-slate-400 dark:text-slate-600', running: 'text-indigo-700 dark:text-indigo-300', done: 'text-emerald-600 dark:text-emerald-400', error: 'text-red-600 dark:text-red-400',
};

// ── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, color }: {
  icon: React.ElementType; label: string; value: string | number; color: string;
}) {
  return (
    <div className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4 flex items-center gap-4 border border-slate-300 dark:border-slate-700">
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-xs text-slate-600 dark:text-slate-400">{label}</div>
        <div className="text-lg font-semibold text-slate-900 dark:text-white">{value}</div>
      </div>
    </div>
  );
}

const fmtBytes = (b: number) => {
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 ** 2).toFixed(1)} MB`;
};

// ── Main Component ────────────────────────────────────────────────────────────

export default function IngestPage() {
  const [docs, setDocs]   = useState<Document[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [uploading, setUploading] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [docsRes, statsRes] = await Promise.all([getDocuments(), getStats()]);
      setDocs(docsRes.data);
      setStats(statsRes.data);
    } catch {}
  }, []);

  // Initial load
  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Poll while any document is processing
  useEffect(() => {
    const hasActive = docs.some((d) => d.status === 'pending' || d.status === 'processing');
    if (!hasActive) return;
    const t = setTimeout(fetchAll, 2000);
    return () => clearTimeout(t);
  }, [docs, fetchAll]);

  const onDrop = useCallback(async (accepted: File[]) => {
    setUploading(true);
    for (const file of accepted) {
      try {
        await uploadDocument(file);
      } catch (e: any) {
        alert(`Upload failed: ${e?.response?.data?.detail ?? e.message}`);
      }
    }
    setUploading(false);
    fetchAll();
  }, [fetchAll]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'text/markdown': ['.md'],
    },
  });

  const handleDelete = async (id: string) => {
    if (!confirm('이 문서와 연관된 위키 페이지를 모두 삭제합니다. 계속할까요?')) return;
    try {
      await deleteDocument(id);
      fetchAll();
    } catch {}
  };

  const doneCount  = docs.filter((d) => d.status === 'done').length;
  const totalCount = docs.length;
  const successRate = totalCount ? Math.round((doneCount / totalCount) * 100) : 0;

  return (
    <div className="flex flex-col h-full p-6 gap-6 overflow-y-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-white">Knowledge Ingest</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">문서를 업로드하여 AI 지식 베이스를 구축합니다</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={Files}    label="총 문서"     value={totalCount}           color="bg-indigo-900/50 text-indigo-600 dark:text-indigo-400" />
        <StatCard icon={Percent}  label="처리 성공률"  value={`${successRate}%`}    color="bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400" />
        <StatCard icon={Database} label="DB 용량"     value={stats ? fmtBytes(stats.db_size_bytes + stats.chroma_size_bytes) : '—'} color="bg-amber-100 dark:bg-amber-900/50 text-amber-600 dark:text-amber-400" />
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20' : 'border-slate-300 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 hover:bg-slate-200/50 dark:hover:bg-slate-800/50'
        }`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <Loader2 className="w-8 h-8 text-indigo-600 dark:text-indigo-400 animate-spin mx-auto mb-3" />
        ) : (
          <Upload className={`w-8 h-8 mx-auto mb-3 ${isDragActive ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-500 dark:text-slate-500'}`} />
        )}
        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {uploading ? '업로드 중...' : isDragActive ? '여기에 파일을 놓으세요' : 'PDF, DOCX, PPTX 파일을 드래그하거나 클릭하세요'}
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">여러 파일 동시 업로드 가능</p>
      </div>

      {/* Document Queue */}
      {docs.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide">처리 큐</h2>
          {docs.map((doc) => {
            const steps = getSteps(doc);
            const isProcessing = doc.status === 'pending' || doc.status === 'processing';
            return (
              <div key={doc.id} className="bg-slate-50 dark:bg-slate-800 rounded-xl p-4 border border-slate-300 dark:border-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="w-5 h-5 text-indigo-600 dark:text-indigo-400 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{doc.filename}</p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">{fmtBytes(doc.file_size)} · {new Date(doc.created_at).toLocaleString('ko-KR')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {doc.status === 'done' && (
                      <span className="text-xs bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded-full font-medium">
                        위키 {doc.wiki_pages_count}개
                      </span>
                    )}
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="p-1.5 text-slate-400 dark:text-slate-600 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Progress bar */}
                {isProcessing && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
                      <span>처리 중...</span>
                      <span>{doc.progress}%</span>
                    </div>
                    <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-1.5">
                      <div
                        className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${doc.progress}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Pipeline steps */}
                <div className="flex items-center gap-3 mt-3">
                  {steps.map((step, i) => (
                    <div key={step.label} className="flex items-center gap-1.5">
                      {i > 0 && <div className="w-4 h-px bg-slate-100 dark:bg-slate-700" />}
                      {stepIcon[step.state]}
                      <span className={`text-xs font-medium ${stepLabel[step.state]}`}>{step.label}</span>
                    </div>
                  ))}
                </div>

                {/* Error message */}
                {doc.status === 'error' && doc.error_message && (
                  <p className="text-xs text-red-600 dark:text-red-400 mt-2 bg-red-50 dark:bg-red-900/20 px-3 py-1.5 rounded-lg">
                    {doc.error_message}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {docs.length === 0 && !uploading && (
        <div className="text-center py-12 text-slate-400 dark:text-slate-600">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">업로드된 문서가 없습니다</p>
        </div>
      )}
    </div>
  );
}
