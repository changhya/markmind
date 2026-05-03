import { useState } from 'react';
import { Settings, Server, Cpu, Moon, Sun, Save, CheckCircle, Brain } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const MODELS = ['llama3', 'llama3.1', 'llama3.2', 'mistral', 'gemma2', 'qwen2', 'phi3'];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-700">
        <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
      </div>
      <div className="p-5 space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-300 mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-slate-600 mt-1">{hint}</p>}
    </div>
  );
}

export default function SettingsPage() {
  const { dark, toggle } = useTheme();

  const [backendUrl, setBackendUrl] = useState(
    () => localStorage.getItem('markmind_backend_url') ?? 'http://127.0.0.1:8000'
  );
  const [defaultModel, setDefaultModel] = useState(
    () => localStorage.getItem('markmind_default_model') ?? 'llama3'
  );
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    localStorage.setItem('markmind_backend_url', backendUrl);
    localStorage.setItem('markmind_default_model', defaultModel);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
    <div className="flex flex-col p-6 gap-6 max-w-2xl pb-10">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Settings className="w-5 h-5 text-indigo-400" />
        <div>
          <h1 className="text-xl font-bold text-white">Settings</h1>
          <p className="text-xs text-slate-400 mt-0.5">로컬 환경 및 AI 모델 설정</p>
        </div>
      </div>

      {/* Backend */}
      <Section title="Backend 연결">
        <Field label="API URL" hint="MarkMind 백엔드 서버 주소 (기본: http://127.0.0.1:8000)">
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 focus-within:border-indigo-500 transition-colors w-full">
            <Server className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <input
              type="text"
              value={backendUrl}
              onChange={(e) => setBackendUrl(e.target.value)}
              className="flex-1 bg-transparent text-base text-white outline-none placeholder-slate-600 py-1.5"
              placeholder="http://127.0.0.1:8000"
            />
          </div>
        </Field>
      </Section>

      {/* LLM Model */}
      <Section title="Edge AI 모델">
        <Field label="기본 Ollama 모델" hint="Ollama에서 pull된 모델 이름을 입력하세요">
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 focus-within:border-indigo-500 transition-colors w-full">
            <Cpu className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <input
              type="text"
              value={defaultModel}
              onChange={(e) => setDefaultModel(e.target.value)}
              list="model-suggestions"
              className="flex-1 bg-transparent text-base text-white outline-none placeholder-slate-600 py-1.5"
              placeholder="llama3"
            />
            <datalist id="model-suggestions">
              {MODELS.map((m) => <option key={m} value={m} />)}
            </datalist>
          </div>
        </Field>

        <div className="grid grid-cols-3 gap-2">
          {MODELS.slice(0, 6).map((m) => (
            <button
              key={m}
              onClick={() => setDefaultModel(m)}
              className={`px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                defaultModel === m
                  ? 'bg-indigo-900/60 border-indigo-500 text-indigo-300'
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </Section>

      {/* Appearance */}
      <Section title="인터페이스">
        <Field label="테마">
          <button
            onClick={toggle}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl border w-full transition-colors ${
              dark
                ? 'bg-slate-900 border-indigo-500 text-indigo-300'
                : 'bg-slate-900 border-slate-600 text-slate-300'
            }`}
          >
            {dark ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
            <span className="text-sm font-medium">{dark ? '다크 모드' : '라이트 모드'}</span>
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${dark ? 'bg-indigo-900 text-indigo-400' : 'bg-amber-900/50 text-amber-400'}`}>
              {dark ? '활성' : '활성'}
            </span>
          </button>
        </Field>
      </Section>

      {/* About */}
      <Section title="시스템 정보">
        <div className="space-y-2 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-indigo-400" />
            <span className="font-medium text-slate-200">MarkMind Edge AI</span>
            <span className="text-slate-600">v0.1.0</span>
          </div>
          <p className="pl-6 text-slate-500">
            Karpathy의 LLM-Wiki 철학 기반 · 100% 로컬 처리 · 클라우드 통신 없음
          </p>
          <div className="pl-6 flex flex-wrap gap-2 mt-2">
            {['FastAPI', 'Ollama', 'ChromaDB', 'MarkItDown', 'React Flow'].map((t) => (
              <span key={t} className="bg-slate-900 border border-slate-700 px-2 py-0.5 rounded text-[10px] text-slate-500">{t}</span>
            ))}
          </div>
        </div>
      </Section>

      {/* Save */}
      <button
        onClick={handleSave}
        className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl px-6 py-3 text-sm font-medium transition-colors"
      >
        {saved ? <CheckCircle className="w-4 h-4 text-emerald-300" /> : <Save className="w-4 h-4" />}
        {saved ? '저장 완료!' : '설정 저장'}
      </button>
    </div>
  );
}
