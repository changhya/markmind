import axios from 'axios';

const getBaseURL = () =>
  localStorage.getItem('markmind_backend_url') ?? 'http://127.0.0.1:8000';

const api = axios.create({ timeout: 120_000 });
api.interceptors.request.use((cfg) => {
  cfg.baseURL = getBaseURL();
  return cfg;
});

export const uploadDocument = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/api/upload', form);
};

export const getDocuments   = ()        => api.get('/api/documents');
export const getDocStatus   = (id: str) => api.get(`/api/documents/${id}/status`);
export const deleteDocument = (id: str) => api.delete(`/api/documents/${id}`);

export const getWikiPages     = (flat = false) => api.get(`/api/wiki?flat=${flat}`);
export const getWikiPage      = (id: str)      => api.get(`/api/wiki/${id}`);
export const updateWikiPage   = (id: str, data: object) => api.put(`/api/wiki/${id}`, data);
export const deleteWikiPage   = (id: str)      => api.delete(`/api/wiki/${id}`);
export const getWikiRevisions = (id: str)            => api.get(`/api/wiki/${id}/revisions`);
export const refineWikiPage   = (id: str, context?: string) =>
  api.post(`/api/wiki/${id}/refine`, { context });
export const mergeWikiPages   = (source_ids: str[], keep_id?: str) =>
  api.post('/api/wiki/merge', { source_ids, keep_id });
export const getDuplicates    = ()                   => api.get('/api/wiki/duplicates');

export const chat            = (query: string, model: string) => api.post('/api/chat', { query, model });
export const getChatHistory  = (limit = 50)         => api.get(`/api/chat/history?limit=${limit}`);
export const getStats        = ()                   => api.get('/api/stats');

export const getBackendURL = () =>
  localStorage.getItem('markmind_backend_url') ?? 'http://127.0.0.1:8000';

type str = string;
export default api;
