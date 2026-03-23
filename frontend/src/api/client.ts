import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const login = async (username: string, password: string) => {
  const res = await api.post('/auth/login', { username, password });
  localStorage.setItem('token', res.data.access_token);
  return res.data;
};

export const logout = () => {
  localStorage.removeItem('token');
};

export const listPapers = async () => {
  const res = await api.get('/papers/');
  return res.data;
};

export const uploadPaper = async (file: File) => {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post('/papers/upload', form);
  return res.data;
};

export const askQuestion = async (
  question: string,
  useExpansion: boolean = false
) => {
  const res = await api.post('/chat/ask', {
    question,
    use_expansion: useExpansion,
    n_chunks: 5,
  });
  return res.data;
};

export const clearHistory = async () => {
  await api.delete('/chat/history');
};

export const isLoggedIn = () => !!localStorage.getItem('token');

export const deletePaper = async (doi: string) => {
  const res = await api.delete(`/papers/${encodeURIComponent(doi)}`);
  return res.data;
};

export const getIndexingStatus = async (filename: string) => {
  const res = await api.get(`/papers/status/${encodeURIComponent(filename)}`);
  return res.data;
};
