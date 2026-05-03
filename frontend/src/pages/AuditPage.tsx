import { useState, useEffect, useCallback } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { History, Clock, User, Bot, ChevronDown, FileText, MessageSquare } from 'lucide-react';
import { getWikiPages, getWikiRevisions, getChatHistory } from '../api/client';
import type { WikiPage, WikiRevision } from '../types';

interface ChatSession {
  id: string;
  query: string;
  response: string;
  sources: { title: string; source: string }[];
  context_used: string[];
  model: string;
  created_at: string;
}

const stripFrontmatter = (text: string) => {
  const m = text.match(/^---\n[\s\S]*?\n---\n?([\s\S]*)$/);
  return m ? m[1].trim() : text;
};

// ── Revision Timeline Item ────────────────────────────────────────────────────

function RevisionItem({ rev, isLatest }: { rev: WikiRevision; isLatest: boolean }) {
  const [open, setOpen] = useState(isLatest);
  return (
    <div className="relative pl-6">
      <div className="absolute left-2 top-4 bottom-0 w-px bg-slate-800" />
      <div className={`absolute left-0.5 top-3.5 w-3 h-3 rounded-full border-2 ${
        rev.revised_by === 'agent' ? 'bg-indigo-500 border-indigo-300' :
        rev.revised_by === 'user'  ? 'bg-emerald-500 border-emerald-300' :
                                     'bg-slate-500 border-slate-300'
      }`} />
      <div className="mb-4">
        <button className="w-full text-left" onClick={() => setOpen((v) => !v)}>
          <div className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-slate-800 transition-colors">
            {rev.revised_by === 'agent'
              ? <Bot  className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
              : <User className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-300">
                {rev.revised_by === 'agent' ? 'AI 정제' : '사용자 편집'}
                {isLatest && <span className="ml-2 text-[10px] bg-indigo-900 text-indigo-400 px-1.5 py-0.5 rounded-full">현재</span>}
              </p>
              <p className="text-[10px] text-slate-600 mt-0.5 flex items-center gap-1">
                <Clock className="w-2.5 h-2.5" />
                {new Date(rev.created_at).toLocaleString('ko-KR')}
              </p>
            </div>
            <ChevronDown className={`w-3.5 h-3.5 text-slate-600 transition-transform ${open ? 'rotate-180' : ''}`} />
          </div>
        </button>
        {open && (
          <div className="mt-2 ml-3 bg-slate-900 border border-slate-800 rounded-xl p-4">
            {rev.summary && (
              <p className="text-xs text-slate-400 italic mb-3 pb-2 border-b border-slate-800">{rev.summary}</p>
            )}
            <div className="prose prose-invert prose-xs max-w-none text-xs prose-headings:text-white prose-headings:text-sm prose-p:text-slate-400 prose-code:text-indigo-300 prose-code:bg-slate-800">
              <Markdown remarkPlugins={[remarkGfm]}>{stripFrontmatter(rev.content)}</Markdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Chat Session (Why-Trail) ──────────────────────────────────────────────────

function ChatSessionItem({ session }: { session: ChatSession }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      <button className="w-full flex items-start gap-3 p-4 hover:bg-slate-800/50 transition-colors text-left"
        onClick={() => setOpen((v) => !v)}>
        <MessageSquare className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-200 truncate">{session.query}</p>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[10px] text-slate-600 flex items-center gap-1">
              <Clock className="w-2.5 h-2.5" />{new Date(session.created_at).toLocaleString('ko-KR')}
            </span>
            <span className="text-[10px] bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded font-mono">{session.model}</span>
            {session.sources.length > 0 && (
              <span className="text-[10px] text-indigo-400">{session.sources.length}개 출처</span>
            )}
          </div>
        </div>
        <ChevronDown className={`w-4 h-4 text-slate-600 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-800 p-4 space-y-4">
          {/* Response */}
          <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">AI 응답</p>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{session.response}</p>
          </div>

          {/* Why-Trail: Sources used */}
          {session.sources.length > 0 && (
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">참조한 위키 문서 (Why-Trail)</p>
              <div className="space-y-2">
                {session.sources.map((s, i) => (
                  <div key={i} className="flex items-start gap-2 bg-slate-800 rounded-lg px-3 py-2">
                    <FileText className="w-3.5 h-3.5 text-indigo-400 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-slate-300">{s.title}</p>
                      <p className="text-[10px] text-slate-500">{s.source}</p>
                      {session.context_used[i] && (
                        <p className="text-[10px] text-slate-600 mt-1 line-clamp-2">
                          {session.context_used[i].slice(0, 200)}…
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

type AuditTab = 'revisions' | 'why-trail';

export default function AuditPage() {
  const [tab, setTab]               = useState<AuditTab>('revisions');
  const [pages, setPages]           = useState<WikiPage[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [revisions, setRevisions]   = useState<WikiRevision[]>([]);
  const [sessions, setSessions]     = useState<ChatSession[]>([]);
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    getWikiPages(true).then(({ data }) => setPages(data)).catch(() => {});
    getChatHistory().then(({ data }) => setSessions(data)).catch(() => {});
  }, []);

  const loadRevisions = useCallback(async (id: string) => {
    setSelectedId(id);
    setLoading(true);
    try {
      const { data } = await getWikiRevisions(id);
      setRevisions(data);
    } catch { setRevisions([]); }
    finally { setLoading(false); }
  }, []);

  const selected = pages.find((p) => p.id === selectedId);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-800 flex items-center gap-3">
        <History className="w-4 h-4 text-indigo-400" />
        <h1 className="text-sm font-semibold text-white">Audit Trail</h1>
        <div className="ml-4 flex gap-1">
          {([['revisions', '편집 이력'], ['why-trail', 'Chat Why-Trail']] as [AuditTab, string][]).map(([t, label]) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                tab === t ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
              }`}>
              {label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-slate-500">
          {tab === 'why-trail' ? `${sessions.length}개 세션` : ''}
        </span>
      </div>

      {tab === 'revisions' ? (
        <div className="flex flex-1 overflow-hidden">
          {/* Page Selector */}
          <aside className="w-64 flex-shrink-0 border-r border-slate-800 overflow-y-auto">
            <div className="p-3 border-b border-slate-800">
              <p className="text-xs font-medium text-slate-400">위키 페이지 선택</p>
            </div>
            <div className="p-2 space-y-0.5">
              {pages.length === 0 && <p className="text-xs text-slate-600 p-3 text-center">위키 페이지 없음</p>}
              {pages.map((p) => (
                <button key={p.id} onClick={() => loadRevisions(p.id)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-xs transition-colors ${
                    selectedId === p.id
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
                  }`}>
                  <FileText className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="truncate">{p.title}</span>
                </button>
              ))}
            </div>
          </aside>

          {/* Revisions */}
          <div className="flex-1 overflow-y-auto p-6">
            {!selectedId && (
              <div className="flex flex-col items-center justify-center h-full text-center gap-3">
                <History className="w-12 h-12 text-slate-800" />
                <p className="text-slate-500 text-sm">좌측에서 페이지를 선택하세요</p>
              </div>
            )}
            {selectedId && selected && (
              <>
                <div className="mb-6">
                  <h2 className="text-lg font-bold text-white">{selected.title}</h2>
                  <p className="text-xs text-slate-500 mt-1">총 {revisions.length}개 버전</p>
                </div>
                {loading ? (
                  <p className="text-xs text-slate-500">로딩 중...</p>
                ) : revisions.length === 0 ? (
                  <div className="text-center py-10">
                    <Clock className="w-8 h-8 text-slate-800 mx-auto mb-2" />
                    <p className="text-xs text-slate-600">아직 편집 이력이 없습니다.</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {revisions.map((rev, i) => (
                      <RevisionItem key={rev.id} rev={rev} isLatest={i === 0} />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      ) : (
        /* ── Why-Trail ── */
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto space-y-3">
            {sessions.length === 0 ? (
              <div className="text-center py-16">
                <MessageSquare className="w-12 h-12 text-slate-800 mx-auto mb-3" />
                <p className="text-slate-500 text-sm">AI Chat 이력이 없습니다.<br />채팅을 시작하면 여기에 기록됩니다.</p>
              </div>
            ) : (
              sessions.map((s) => <ChatSessionItem key={s.id} session={s} />)
            )}
          </div>
        </div>
      )}
    </div>
  );
}
