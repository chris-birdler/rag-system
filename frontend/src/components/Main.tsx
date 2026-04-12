import React, { useState } from 'react';
import { logout } from '../api/client';
import PaperList from './PaperList';
import Chat from './Chat';
import './Main.css';

interface Props {
  onLogout: () => void;
}

export default function Main({ onLogout }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    onLogout();
  };

  return (
    <div className="main">
      <div className="main-header">
        <div className="main-header-left">
          <button
            className="main-menu-btn"
            onClick={() => setSidebarOpen(v => !v)}
            aria-label={sidebarOpen ? 'Close papers menu' : 'Open papers menu'}
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? '\u2715' : '\u2630'}
          </button>
          <h1 className="main-title">
            📚 RAG System
          </h1>
        </div>
        <button
          className="main-logout-btn"
          onClick={handleLogout}
        >
          Logout
        </button>
      </div>

      <div className="main-content">
        {sidebarOpen && (
          <div
            className="main-backdrop"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <div className={`main-sidebar${sidebarOpen ? ' main-sidebar--open' : ''}`}>
          <PaperList />
        </div>
        <div className="main-chat">
          <Chat />
        </div>
      </div>
    </div>
  );
}
