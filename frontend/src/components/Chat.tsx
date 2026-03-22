import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { askQuestion, clearHistory } from '../api/client';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {messages.length === 0 && (
          <div style={{
            textAlign: 'center',
            color: '#555',
            marginTop: '40px',
            fontSize: '16px',
          }}>
            Ask a question about your papers...
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} style={{
            padding: '16px',
            borderRadius: '12px',
            maxWidth: msg.role === 'user' ? '80%' : '90%',
            background: msg.role === 'user' ? '#0f3460' : '#16213e',
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            color: msg.role === 'user' ? 'white' : '#e0e0e0',
            fontSize: '14px',
            lineHeight: '1.6',
          }}>
            <div style={{
              fontSize: '11px',
              color: '#888',
              marginBottom: '8px',
              fontWeight: 'bold',
            }}>
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
          <div style={{
            padding: '16px',
            borderRadius: '12px',
            background: '#16213e',
            alignSelf: 'flex-start',
            color: '#888',
            fontStyle: 'italic',
            fontSize: '14px',
          }}>
            <div style={{ fontSize: '11px', color: '#888', marginBottom: '8px', fontWeight: 'bold' }}>
              🤖 Assistant
            </div>
            Thinking...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Sources */}
      {sources.length > 0 && (
        <div style={{
          padding: '12px 24px',
          borderTop: '1px solid #333',
          background: '#16213e',
          display: 'flex',
          gap: '12px',
          flexWrap: 'wrap',
          alignItems: 'center',
        }}>
          <span style={{ fontSize: '11px', color: '#888', fontWeight: 'bold' }}>
            Sources
          </span>
          {sources.map((s, i) => (
            <div key={i} style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'center',
              background: '#0f3460',
              padding: '6px 10px',
              borderRadius: '6px',
              fontSize: '11px',
            }}>
              <span style={{ color: 'white' }}>
                {s.authors.split(';')[0].split(',')[0].trim()} et al. ({s.year})
              </span>
              <span style={{ color: '#888' }}>Page {s.page} · {s.section}</span>
              {s.doi && (
                <a
                  href={`https://doi.org/${s.doi}`}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: '#e94560', textDecoration: 'none', fontWeight: 'bold' }}
                >
                  DOI
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{
        padding: '16px 24px',
        borderTop: '1px solid #333',
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        background: '#16213e',
      }}>
        <button
          style={{
            padding: '12px 16px',
            background: 'transparent',
            border: '1px solid #555',
            borderRadius: '8px',
            color: '#888',
            cursor: 'pointer',
            fontSize: '14px',
          }}
          onClick={handleClear}
        >
          Clear
        </button>
        <input
          style={{
            flex: 1,
            padding: '12px 16px',
            borderRadius: '8px',
            border: '1px solid #333',
            background: '#0f3460',
            color: 'white',
            fontSize: '14px',
            outline: 'none',
          }}
          placeholder="Ask about your papers..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAsk()}
          disabled={loading}
        />
        <button
          style={{
            padding: '12px 24px',
            background: loading || !input.trim() ? '#555' : '#e94560',
            border: 'none',
            borderRadius: '8px',
            color: 'white',
            cursor: loading || !input.trim() ? 'default' : 'pointer',
            fontWeight: 'bold',
            fontSize: '14px',
          }}
          onClick={handleAsk}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
