import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { askQuestion, clearHistory } from '../api/client';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './Chat.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Source {
  title: string;
  authors: string;
  year: string;
  doi: string;
  page: number;
  section: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleAsk = async () => {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput('');
    setLoading(true);
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    try {
      const result = await askQuestion(question);
      setMessages(prev => [...prev, { role: 'assistant', content: result.answer }]);
      setSources(result.sources);
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error: Could not get response.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    await clearHistory();
    setMessages([]);
    setSources([]);
  };

  const processLatex = (content: string): string => {
    return content
      .replace(/\\\[(.*?)\\\]/gs, '$$$$\n$1\n$$$$')
      .replace(/\\\((.*?)\\\)/gs, '$$$1$$');
  };

  return (
    <div className="chat">

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            Ask a question about your papers...
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-role">
              {msg.role === 'user' ? '👤 You' : '🤖 Assistant'}
            </div>

            <ReactMarkdown
              remarkPlugins={[remarkMath]}
              rehypePlugins={[rehypeKatex]}
            >
              {processLatex(msg.content)}
            </ReactMarkdown>

          </div>
        ))}

        {loading && (
          <div className="chat-loading">
            <div className="chat-message-role">
              🤖 Assistant
            </div>
            Thinking...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Sources */}
      {sources.length > 0 && (
        <div className="chat-sources">
          <span className="chat-sources-label">
            Sources
          </span>
          {sources.map((s, i) => (
            <div key={i} className="chat-source">
              <span className="chat-source-author">
                {s.authors.split(';')[0].split(',')[0].trim()} et al. ({s.year})
              </span>
              <span className="chat-source-detail">Page {s.page} · {s.section}</span>
              {s.doi && (
                <a
                  href={`https://doi.org/${s.doi}`}
                  target="_blank"
                  rel="noreferrer"
                  className="chat-source-doi"
                >
                  DOI
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="chat-input-bar">
        <button
          className="chat-clear-btn"
          onClick={handleClear}
        >
          Clear
        </button>
        <input
          className="chat-input"
          placeholder="Ask about your papers..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAsk()}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={handleAsk}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
