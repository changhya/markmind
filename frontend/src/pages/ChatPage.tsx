import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, MessageSquare, FileText, Cpu, BookOpen } from 'lucide-react';
import { getBackendURL } from '../api/client';
import type { ChatMessage } from '../types';

const MODELS = ['llama3', 'llama3.1', 'mistral', 'gemma2', 'qwen2'];

// ── Message Bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage & { streaming?: boolean } }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold ${
        isUser ? 'bg-indigo-600 text-white' : 'bg-slate-700 text-slate-300'
      }`}>{isUser ? 'U' : 'AI'}</div>

      <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'bg-indigo-600 text-white rounded-tr-sm'
          : 'bg-slate-800 text-slate-100 rounded-tl-sm border border-slate-700'
      }`}>
        <span className="whitespace-pre-wrap">{msg.content}</span>
        {(msg as any).streaming && (
          <span className="inline-block w-2 h-4 bg-indigo-400 ml-0.5 animate-pulse rounded-sm" />
        )}

        {!isUser && msg.sources && msg.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-slate-700">
            {msg.sources.map((s, i) => (
              <span key={i} className="text-[10px] bg-slate-700 text-slate-400 px-2 py-0.5 rounded-full flex items-center gap-1">
                <FileText className="w-2.5 h-2.5" />{s.title || s.source}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Reference Card ────────────────────────────────────────────────────────────

function ReferenceCard({ title, source, snippet }: { title: string; source: string; snippet: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 cursor-pointer hover:border-indigo-500 transition-colors"
         onClick={() => setOpen((o) => !o)}>
      <div className="flex items-start gap-2">
        <FileText className="w-3.5 h-3.5 text-indigo-400 mt-0.5 flex-shrink-0" />
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-200 truncate">{title || source}</p>
          <p className="text-[10px] text-slate-500 truncate">{source}</p>
        </div>
      </div>
      {open && (
        <p className="text-xs text-slate-400 mt-2 pt-2 border-t border-slate-700 line-clamp-6">{snippet}</p>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

type ExtendedMsg = ChatMessage & { streaming?: boolean };

export default function ChatPage() {
  const [messages, setMessages]         = useState<ExtendedMsg[]>([]);
  const [input, setInput]               = useState('');
  const [loading, setLoading]           = useState(false);
  const [model, setModel]               = useState(() => localStorage.getItem('markmind_default_model') ?? 'llama3');
  const [currentRefs, setCurrentRefs]   = useState<{ title: string; source: string; snippet: string }[]>([]);
  const bottomRef                        = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const query = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: query }]);
    setLoading(true);

    // Add empty streaming assistant message
    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }]);

    try {
      const res = await fetch(`${getBackendURL()}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, model }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader  = res.body!.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let msgSources: { title: string; source: string }[] = [];
      let contextDocs: string[] = [];
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.sources != null) {
              msgSources  = data.sources;
              contextDocs = data.context_used ?? [];
              setCurrentRefs(
                (data.sources as { title: string; source: string }[]).map((s, i) => ({
                  title: s.title, source: s.source, snippet: contextDocs[i] ?? '',
                }))
              );
            }

            if (data.token != null) {
              accumulated += data.token;
              setMessages((prev) => prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, content: accumulated } : m
              ));
            }

            if (data.done) {
              setMessages((prev) => prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, sources: msgSources, streaming: false } : m
              ));
            }

            if (data.error) {
              setMessages((prev) => prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, content: `오류: ${data.error}`, streaming: false } : m
              ));
            }
          } catch {}
        }
      }
    } catch (e: any) {
      setMessages((prev) => prev.map((m, i) =>
        i === prev.length - 1
          ? { ...m, content: `오류가 발생했습니다: ${e.message}`, streaming: false }
          : m
      ));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Chat (2/3) ── */}
      <div className="flex-1 flex flex-col overflow-hidden border-r border-slate-800">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center gap-3">
          <MessageSquare className="w-4 h-4 text-indigo-400" />
          <h1 className="text-sm font-semibold text-white">AI Chat Explorer</h1>
          <span className="ml-auto text-xs text-slate-500">RAG + SSE 스트리밍</span>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4">
              <BookOpen className="w-12 h-12 text-slate-700" />
              <div>
                <p className="text-slate-400 font-medium">지식 베이스에 질문하세요</p>
                <p className="text-slate-600 text-sm mt-1">응답이 실시간으로 스트리밍됩니다</p>
              </div>
            </div>
          )}
          {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
          <div ref={bottomRef} />
        </div>

        <div className="px-6 py-4 border-t border-slate-800 space-y-3">
          <div className="flex gap-3">
            <input
              className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              placeholder="질문을 입력하세요... (Enter로 전송)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              disabled={loading}
            />
            <button onClick={sendMessage} disabled={!input.trim() || loading}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl px-4 py-2.5 transition-colors flex items-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>

          <div className="flex items-center gap-3">
            <Cpu className="w-3.5 h-3.5 text-slate-600" />
            <span className="text-xs text-slate-600">Model:</span>
            <select value={model}
              onChange={(e) => { setModel(e.target.value); localStorage.setItem('markmind_default_model', e.target.value); }}
              className="text-xs bg-transparent text-slate-400 border-none outline-none cursor-pointer">
              {MODELS.map((m) => <option key={m} value={m} className="bg-slate-900">{m}</option>)}
            </select>
            <span className="ml-auto text-xs text-emerald-600 font-medium">● Local Inference</span>
          </div>
        </div>
      </div>

      {/* ── References (1/3) ── */}
      <div className="w-72 flex-shrink-0 flex flex-col overflow-hidden">
        <div className="px-4 py-4 border-b border-slate-800">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">참조 문서</h2>
          <p className="text-[10px] text-slate-600 mt-0.5">답변 생성에 사용된 위키 페이지</p>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {currentRefs.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="w-8 h-8 text-slate-800 mx-auto mb-2" />
              <p className="text-xs text-slate-600">질문을 보내면<br />참조 문서가 표시됩니다</p>
            </div>
          ) : (
            currentRefs.map((ref, i) => <ReferenceCard key={i} {...ref} />)
          )}
        </div>
      </div>
    </div>
  );
}
