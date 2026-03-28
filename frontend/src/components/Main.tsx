import React from 'react';
import { logout } from '../api/client';
import PaperList from './PaperList';
import Chat from './Chat';
import './Main.css';

interface Props {
  onLogout: () => void;
}

export default function Main({ onLogout }: Props) {
  const handleLogout = () => {
    logout();
    onLogout();
  };

  return (
    <div className="main">
      <div className="main-header">
        <h1 className="main-title">
          📚 RAG System
        </h1>
        <button
          className="main-logout-btn"
          onClick={handleLogout}
        >
          Logout
        </button>
      </div>

      <div className="main-content">
        <div className="main-sidebar">
          <PaperList />
        </div>
        <div className="main-chat">
          <Chat />
        </div>
      </div>
    </div>
  );
}
