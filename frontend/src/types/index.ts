export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface Source {
  title: string;
  authors: string;
  year: string;
  doi: string;
  page: number;
  section: string;
  relevance: number;
}

export interface AnswerResponse {
  question: string;
  answer: string;
  sources: Source[];
}

export interface Paper {
  filename: string;
  title: string;
  authors: string;
  year: string;
  doi: string;
}
