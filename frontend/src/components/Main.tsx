import React from 'react';
import { logout } from '../api/client';
import PaperList from './PaperList';
import Chat from './Chat';

interface Props {
  onLogout: () => void;
}

export default function Main({ onLogout }: Props) {
  const handleLogout = () => {
    logout();
    onLogout();
  };

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#1a1a2e',
      color: 'white',
    }}>
      <div style={{
        padding: '16px 24px',
        background: '#16213e',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid #333',
      }}>
        <h1 style={{ margin: 0, fontSize: '20px', color: 'white' }}>
          📚 RAG System
        </h1>
        <button
          style={{
            padding: '8px 16px',
            background: 'transparent',
            border: '1px solid #555',
            borderRadius: '6px',
            color: '#aaa',
            cursor: 'pointer',
          }}
          onClick={handleLogout}
        >
          Logout
        </button>
      </div>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <div style={{ width: '280px', borderRight: '1px solid #333', overflow: 'auto' }}>
          <PaperList />
        </div>
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Chat />
        </div>
      </div>
    </div>
  );
}
