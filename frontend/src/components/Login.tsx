import React, { useState } from 'react';
import { login } from '../api/client';

interface Props {
  onLogin: () => void;
}

export default function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      await login(username, password);
      onLogin();
    } catch {
      setError('Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#1a1a2e',
    }}>
      <div style={{
        background: '#16213e',
        padding: '40px',
        borderRadius: '12px',
        width: '360px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        <h1 style={{ color: 'white', margin: 0, fontSize: '24px', textAlign: 'center' }}>
          RAG System
        </h1>
        <p style={{ color: '#888', margin: 0, textAlign: 'center', fontSize: '14px' }}>
          Scientific Paper Assistant
        </p>
        <input
          style={{
            padding: '12px',
            borderRadius: '8px',
            border: '1px solid #333',
            background: '#0f3460',
            color: 'white',
            fontSize: '14px',
          }}
          placeholder="Username"
          value={username}
          onChange={e => setUsername(e.target.value)}
        />
        <input
          style={{
            padding: '12px',
            borderRadius: '8px',
            border: '1px solid #333',
            background: '#0f3460',
            color: 'white',
            fontSize: '14px',
          }}
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleLogin()}
        />
        {error && (
          <p style={{ color: '#e94560', margin: 0, fontSize: '14px', textAlign: 'center' }}>
            {error}
          </p>
        )}
        <button
          style={{
            padding: '12px',
            borderRadius: '8px',
            border: 'none',
            background: '#e94560',
            color: 'white',
            fontSize: '16px',
            cursor: 'pointer',
            fontWeight: 'bold',
          }}
          onClick={handleLogin}
          disabled={loading}
        >
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </div>
    </div>
  );
}
