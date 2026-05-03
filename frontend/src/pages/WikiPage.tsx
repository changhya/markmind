import { useState, useEffect, useCallback } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState,
  Handle, Position,
  type Node, type Edge, type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  FileText, ChevronRight, Tag, Edit2, Save, X,
  Network, BookOpen, Loader2, Trash2, Sparkles,
  GitMerge, CheckSquare, Square, AlertTriangle,
} from 'lucide-react';
import {
  getWikiPages, getWikiPage, updateWikiPage, deleteWikiPage,
  refineWikiPage, mergeWikiPages, getDuplicates,
} from '../api/client';
import type { WikiPage } from '../types';

// ── Helpers ──────────────────────────────────────────────────────────────────

const stripFrontmatter = (text: string) => {
  const m = text.match(/^---\n[\s\S]*?\n---\n?([\s\S]*)$/);
  return m ? m[1].trim() : text;
};

// ── Tree Item ─────────────────────────────────────────────────────────────────

function TreeItem({
  page, depth, selectedId, onSelect, mergeMode, mergeIds, onToggleMerge,
}: {
  page: WikiPage; depth: number; selectedId: string | null;
  onSelect: (id: string) => void;
  mergeMode: boolean; mergeIds: string[];
  onToggleMerge: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = (page.children?.length ?? 0) > 0;
  const inMerge = mergeIds.includes(page.id);

  return (
    <div>
      <div
        className={`flex items-center gap-1.5 py-1.5 pr-2 rounded-lg cursor-pointer text-sm transition-colors ${
          selectedId === page.id && !mergeMode
            ? 'bg-indigo-600 text-white'
            : inMerge
            ? 'bg-amber-900/40 text-amber-300'
            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
        }`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => mergeMode ? onToggleMerge(page.id) : onSelect(page.id)}
      >
        {mergeMode ? (
          <button className="flex-shrink-0" onClick={(e) => { e.stopPropagation(); onToggleMerge(page.id); }}>
            {inMerge
              ? <CheckSquare className="w-3.5 h-3.5 text-amber-400" />
              : <Square      className="w-3.5 h-3.5 text-slate-600" />}
          </button>
        ) : hasChildren ? (
          <button className="flex-shrink-0" onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}>
            <ChevronRight className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`} />
          </button>
        ) : (
          <span className="w-3" />
        )}
        <FileText className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="truncate text-xs">{page.title}</span>
      </div>
      {expanded && hasChildren &&
        page.children!.map((child) => (
          <TreeItem key={child.id} page={child} depth={depth + 1}
            selectedId={selectedId} onSelect={onSelect}
            mergeMode={mergeMode} mergeIds={mergeIds} onToggleMerge={onToggleMerge} />
        ))}
    </div>
  );
}

// ── React Flow Node ───────────────────────────────────────────────────────────

function WikiNode({ data }: NodeProps) {
  const d = data as { title: string; tags: string[]; isDuplicate: boolean };
  return (
    <div className={`px-3 py-2 rounded-xl border shadow-lg min-w-[160px] max-w-[200px] ${
      d.isDuplicate ? 'bg-amber-900/40 border-amber-600' : 'bg-slate-800 border-slate-600'
    }`}>
      <Handle type="target" position={Position.Left}  className="!bg-indigo-500 !border-indigo-700" />
      {d.isDuplicate && <AlertTriangle className="w-3 h-3 text-amber-400 absolute -top-1.5 -right-1.5" />}
      <p className="text-xs font-semibold text-white leading-snug truncate">{d.title}</p>
      <div className="flex flex-wrap gap-1 mt-1">
        {(d.tags ?? []).slice(0, 2).map((t: string) => (
          <span key={t} className="text-[9px] bg-indigo-900/60 text-indigo-300 px-1.5 py-0.5 rounded-full">{t}</span>
        ))}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-indigo-500 !border-indigo-700" />
    </div>
  );
}
const NODE_TYPES = { wiki: WikiNode };

// ── Graph Builder ─────────────────────────────────────────────────────────────

function buildGraph(pages: WikiPage[], selectedId: string | null, duplicateIds: Set<string>) {
  const COLS = 4;
  const nodes: Node[] = pages.map((p, i) => ({
    id: p.id,
    type: 'wiki' as const,
    position: { x: (i % COLS) * 250, y: Math.floor(i / COLS) * 150 },
    data: { title: p.title, tags: p.tags, selected: p.id === selectedId, isDuplicate: duplicateIds.has(p.id) },
  }));

  const edges: Edge[] = [];
  for (let i = 0; i < pages.length; i++) {
    for (let j = i + 1; j < pages.length; j++) {
      if (pages[i].tags.some((t) => pages[j].tags.includes(t))) {
        edges.push({
          id: `e-${pages[i].id}-${pages[j].id}`,
          source: pages[i].id, target: pages[j].id,
          style: { stroke: '#4f46e5', strokeWidth: 1.5, opacity: 0.5 },
        });
      }
    }
  }
  return { nodes, edges };
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function Toast({ msg, type }: { msg: string; type: 'success' | 'error' }) {
  return (
    <div className={`fixed bottom-6 right-6 px-4 py-3 rounded-xl text-sm font-medium shadow-xl z-50 ${
      type === 'success' ? 'bg-emerald-800 text-emerald-100' : 'bg-red-800 text-red-100'
    }`}>
      {msg}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function WikiPage() {
  const [tab, setTab]                 = useState<'wiki' | 'graph'>('wiki');
  const [treePages, setTreePages]     = useState<WikiPage[]>([]);
  const [flatPages, setFlatPages]     = useState<WikiPage[]>([]);
  const [selectedId, setSelectedId]   = useState<string | null>(null);
  const [detail, setDetail]           = useState<WikiPage | null>(null);
  const [loading, setLoading]         = useState(false);

  // Edit state
  const [editing, setEditing]         = useState(false);
  const [editContent, setEditContent] = useState('');
  const [editTitle, setEditTitle]     = useState('');
  const [saving, setSaving]           = useState(false);

  // Refine state
  const [refining, setRefining]       = useState(false);

  // Merge state
  const [mergeMode, setMergeMode]     = useState(false);
  const [mergeIds, setMergeIds]       = useState<string[]>([]);
  const [merging, setMerging]         = useState(false);

  // Duplicate detection
  const [duplicateIds, setDuplicateIds] = useState<Set<string>>(new Set());

  // Toast
  const [toast, setToast]             = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchPages = useCallback(async () => {
    const [treeRes, flatRes] = await Promise.all([getWikiPages(false), getWikiPages(true)]);
    setTreePages(treeRes.data);
    setFlatPages(flatRes.data);
  }, []);

  useEffect(() => { fetchPages(); }, [fetchPages]);

  useEffect(() => {
    if (tab === 'graph' && flatPages.length > 0) {
      const { nodes: n, edges: e } = buildGraph(flatPages, selectedId, duplicateIds);
      setNodes(n); setEdges(e);
    }
  }, [tab, flatPages, selectedId, duplicateIds, setNodes, setEdges]);

  const selectPage = async (id: string) => {
    setSelectedId(id);
    setEditing(false);
    setLoading(true);
    try {
      const { data } = await getWikiPage(id);
      setDetail(data);
    } catch {}
    finally { setLoading(false); }
  };

  // ── Edit ──
  const startEdit = () => {
    if (!detail) return;
    setEditTitle(detail.title);
    setEditContent(stripFrontmatter(detail.content ?? ''));
    setEditing(true);
  };

  const saveEdit = async () => {
    if (!detail) return;
    setSaving(true);
    try {
      await updateWikiPage(detail.id, { title: editTitle, content: editContent });
      await selectPage(detail.id);
      setEditing(false);
      fetchPages();
      showToast('저장 완료');
    } catch { showToast('저장 실패', 'error'); }
    finally { setSaving(false); }
  };

  // ── Refine ──
  const handleRefine = async () => {
    if (!detail) return;
    setRefining(true);
    try {
      await refineWikiPage(detail.id);
      await selectPage(detail.id);
      fetchPages();
      showToast('AI 정제 완료');
    } catch { showToast('정제 실패', 'error'); }
    finally { setRefining(false); }
  };

  // ── Merge ──
  const toggleMergeId = (id: string) =>
    setMergeIds((prev) => prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]);

  const handleMerge = async () => {
    if (mergeIds.length < 2) return;
    setMerging(true);
    try {
      const { data } = await mergeWikiPages(mergeIds);
      setMergeMode(false);
      setMergeIds([]);
      await fetchPages();
      selectPage(data.id);
      showToast(`${data.merged_count}개 페이지 병합 완료`);
    } catch { showToast('병합 실패', 'error'); }
    finally { setMerging(false); }
  };

  // ── Duplicates ──
  const handleFindDuplicates = async () => {
    try {
      const { data } = await getDuplicates();
      const ids = new Set<string>();
      for (const group of data) {
        ids.add(group.source.id);
        group.similar.forEach((s: { id: string }) => ids.add(s.id));
      }
      setDuplicateIds(ids);
      showToast(ids.size > 0 ? `${ids.size}개의 유사 페이지 발견` : '중복 없음');
    } catch { showToast('분석 실패', 'error'); }
  };

  // ── Delete ──
  const handleDelete = async () => {
    if (!detail || !confirm(`"${detail.title}" 페이지를 삭제합니다.`)) return;
    await deleteWikiPage(detail.id);
    setDetail(null); setSelectedId(null);
    fetchPages();
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {toast && <Toast {...toast} />}

      {/* ── Tabs + Actions ── */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-slate-800 flex-wrap">
        {(['wiki', 'graph'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              tab === t ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
            }`}>
            {t === 'wiki' ? <BookOpen className="w-4 h-4" /> : <Network className="w-4 h-4" />}
            {t === 'wiki' ? 'Wiki View' : 'Graph View'}
          </button>
        ))}

        <div className="h-5 w-px bg-slate-700 mx-1" />

        {/* Merge mode toggle */}
        <button onClick={() => { setMergeMode((v) => !v); setMergeIds([]); }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            mergeMode ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-100 border border-slate-700'
          }`}>
          <GitMerge className="w-3.5 h-3.5" />
          {mergeMode ? '병합 취소' : '병합 모드'}
        </button>

        {mergeMode && mergeIds.length >= 2 && (
          <button onClick={handleMerge} disabled={merging}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-600 hover:bg-amber-500 text-white transition-colors disabled:opacity-50">
            {merging ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <GitMerge className="w-3.5 h-3.5" />}
            {mergeIds.length}개 병합
          </button>
        )}

        {/* Find duplicates */}
        <button onClick={handleFindDuplicates}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
            duplicateIds.size > 0
              ? 'bg-amber-900/30 border-amber-700 text-amber-400'
              : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-100'
          }`}>
          <AlertTriangle className="w-3.5 h-3.5" />
          {duplicateIds.size > 0 ? `유사 ${duplicateIds.size}개` : '중복 탐지'}
        </button>

        <span className="ml-auto text-xs text-slate-500">{flatPages.length}개 페이지</span>
      </div>

      {tab === 'wiki' ? (
        <div className="flex flex-1 overflow-hidden">
          {/* ── Tree Sidebar ── */}
          <aside className="w-60 flex-shrink-0 overflow-y-auto border-r border-slate-800 p-2">
            {mergeMode && (
              <div className="mb-2 px-2 py-1.5 bg-amber-900/20 border border-amber-800 rounded-lg">
                <p className="text-[10px] text-amber-400">페이지를 선택하여 병합하세요 ({mergeIds.length}개 선택됨)</p>
              </div>
            )}
            {treePages.length === 0 ? (
              <div className="text-center py-12 text-slate-700">
                <FileText className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-xs">위키 페이지 없음</p>
              </div>
            ) : treePages.map((p) => (
              <TreeItem key={p.id} page={p} depth={0} selectedId={selectedId} onSelect={selectPage}
                mergeMode={mergeMode} mergeIds={mergeIds} onToggleMerge={toggleMergeId} />
            ))}
          </aside>

          {/* ── Content ── */}
          <div className="flex-1 overflow-y-auto p-6">
            {loading && (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">로딩 중...</span>
              </div>
            )}

            {!loading && !detail && (
              <div className="flex flex-col items-center justify-center h-full text-center gap-3">
                <BookOpen className="w-12 h-12 text-slate-800" />
                <p className="text-slate-500 text-sm">좌측에서 페이지를 선택하세요</p>
              </div>
            )}

            {!loading && detail && (
              <>
                {/* Header */}
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div className="min-w-0 flex-1">
                    {editing ? (
                      <input
                        className="text-2xl font-bold bg-transparent border-b border-indigo-500 text-white w-full outline-none pb-1"
                        value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                      />
                    ) : (
                      <h1 className="text-2xl font-bold text-white">{detail.title}</h1>
                    )}
                    <p className="text-xs text-slate-500 mt-1">
                      마지막 수정: {new Date(detail.updated_at).toLocaleString('ko-KR')}
                      {duplicateIds.has(detail.id) && (
                        <span className="ml-2 text-amber-400 font-medium flex items-center gap-1 inline-flex">
                          <AlertTriangle className="w-3 h-3" />유사 페이지 존재
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {editing ? (
                      <>
                        <button onClick={saveEdit} disabled={saving}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50">
                          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                          저장
                        </button>
                        <button onClick={() => setEditing(false)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-xs font-medium transition-colors">
                          <X className="w-3.5 h-3.5" /> 취소
                        </button>
                      </>
                    ) : (
                      <>
                        {/* Refine with AI */}
                        <button onClick={handleRefine} disabled={refining}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-900/60 hover:bg-indigo-800 text-indigo-300 rounded-lg text-xs font-medium transition-colors border border-indigo-700 disabled:opacity-50">
                          {refining ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                          AI 정제
                        </button>
                        <button onClick={startEdit}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors border border-slate-700">
                          <Edit2 className="w-3.5 h-3.5" /> 편집
                        </button>
                        <button onClick={handleDelete}
                          className="p-1.5 text-slate-600 hover:text-red-400 hover:bg-red-900/20 rounded-lg transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap gap-2 mb-5">
                  {detail.tags.map((tag) => (
                    <span key={tag} className="flex items-center gap-1 text-xs bg-indigo-900/40 text-indigo-300 border border-indigo-800 px-2.5 py-1 rounded-full">
                      <Tag className="w-3 h-3" />{tag}
                    </span>
                  ))}
                  {detail.summary && (
                    <span className="text-xs bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-1 rounded-full">
                      {detail.summary.slice(0, 60)}{detail.summary.length > 60 ? '…' : ''}
                    </span>
                  )}
                </div>

                {/* Refining overlay */}
                {refining && (
                  <div className="flex items-center gap-3 mb-4 px-4 py-3 bg-indigo-900/30 border border-indigo-800 rounded-xl">
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                    <span className="text-sm text-indigo-300">AI가 내용을 정제하는 중...</span>
                  </div>
                )}

                {/* Content */}
                {editing ? (
                  <textarea
                    className="w-full h-96 bg-slate-900 border border-slate-700 rounded-xl p-4 text-sm text-slate-100 font-mono resize-none focus:outline-none focus:border-indigo-500 transition-colors"
                    value={editContent} onChange={(e) => setEditContent(e.target.value)}
                  />
                ) : (
                  <div className="prose prose-invert prose-sm max-w-none prose-headings:text-white prose-a:text-indigo-400 prose-code:text-indigo-300 prose-code:bg-slate-800 prose-pre:bg-slate-900">
                    <Markdown remarkPlugins={[remarkGfm]}>
                      {stripFrontmatter(detail.content ?? '')}
                    </Markdown>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      ) : (
        /* ── Graph ── */
        <div className="flex-1 bg-slate-950">
          {flatPages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3">
              <Network className="w-12 h-12 text-slate-800" />
              <p className="text-slate-500 text-sm">위키 페이지가 없습니다.</p>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes} edges={edges}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              nodeTypes={NODE_TYPES}
              onNodeClick={(_, node) => { setTab('wiki'); selectPage(node.id); }}
              fitView proOptions={{ hideAttribution: true }}
            >
              <Background color="#334155" gap={24} size={1} />
              <Controls className="!bg-slate-800 !border-slate-700 !shadow-none" />
              <MiniMap nodeColor={(n) => (n.data as any).isDuplicate ? '#d97706' : '#4f46e5'}
                maskColor="rgba(2,6,23,0.7)" className="!bg-slate-900 !border-slate-700" />
            </ReactFlow>
          )}
        </div>
      )}
    </div>
  );
}
