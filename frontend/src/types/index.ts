export interface Document {
  id: string;
  filename: string;
  original_path: string;
  file_size: number;
  mime_type: string;
  status: 'pending' | 'processing' | 'done' | 'error';
  progress: number;
  error_message: string | null;
  wiki_pages_count: number;
  created_at: string;
  updated_at: string;
}

export interface WikiPage {
  id: string;
  title: string;
  summary: string | null;
  tags: string[];
  content?: string;
  file_path: string | null;
  parent_id: string | null;
  document_id: string | null;
  chroma_id: string | null;
  created_at: string;
  updated_at: string;
  children?: WikiPage[];
}

export interface WikiRevision {
  id: string;
  wiki_page_id: string;
  content: string;
  summary: string | null;
  revised_by: string;
  created_at: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: { title: string; source: string }[];
  context?: string[];
}

export interface Stats {
  total_documents: number;
  total_wiki_pages: number;
  documents_by_status: Record<string, number>;
  db_size_bytes: number;
  chroma_size_bytes: number;
  recent_documents: Partial<Document>[];
  recent_wiki_pages: Partial<WikiPage>[];
}
