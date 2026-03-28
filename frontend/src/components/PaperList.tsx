import React, { useState, useEffect, useRef } from 'react';
import { listPapers, uploadPaper, deletePaper, getIndexingStatus } from '../api/client';
import './PaperList.css';

interface Paper {
  filename: string;
  title: string;
  authors: string;
  year: string;
  doi: string;
}

export default function PaperList() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadPapers();
  }, []);

  const loadPapers = async () => {
    try {
      const data = await listPapers();
      setPapers(data);
    } catch {}
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage('Uploading...');

    try {
      // Upload – bekommt sofort Antwort
      await uploadPaper(file);
      setMessage('Indexing in background...');

      // Pollen bis fertig
      const poll = setInterval(async () => {
        try {
          const status = await getIndexingStatus(file.name);
          if (status.status === 'done') {
            setMessage(`✅ '${file.name}' indexed (${status.chunks} chunks)`);
            clearInterval(poll);
            setUploading(false);
            loadPapers();
          } else if (status.status === 'failed') {
            setMessage(`❌ Indexing failed: ${status.error}`);
            clearInterval(poll);
            setUploading(false);
          } else if (status.status === 'already_indexed') {
            setMessage(`'${file.name}' already indexed`);
            clearInterval(poll);
            setUploading(false);
          }
        } catch {}
      }, 2000); // alle 2 Sekunden prüfen

    } catch {
      setMessage('Upload failed');
      setUploading(false);
    }
  };

  // Delete Handler
const handleDelete = async (doi: string) => {
  if (!window.confirm('Delete this paper?')) return;
  try {
    await deletePaper(doi);
    loadPapers();
  } catch {
    alert('Delete failed');
  }
};

  return (
    <div className="paper-list">
      <div className="paper-list-header">
        <span>Papers ({papers.length})</span>
        <button
          className="paper-list-upload-btn"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? '...' : '+ Upload'}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          style={{ display: 'none' }}
          onChange={handleUpload}
        />
      </div>

      {message && (
        <p className="paper-list-message">
          {message}
        </p>
      )}

      <div className="paper-list-content">
        {papers.map(paper => (
          <div
            key={paper.doi || paper.filename}
            className="paper-card"
          >
            <div className="paper-info">
              <div className="paper-title">
                {paper.title
                  ? paper.title.substring(0, 60) + (paper.title.length > 60 ? '...' : '')
                  : paper.filename}
              </div>
              <div className="paper-meta">
                {paper.year && `${paper.year} · `}
                {paper.authors
                  ? paper.authors.split(';')[0].split(',')[0].trim() + ' et al.'
                  : ''}
              </div>
            </div>
            {paper.doi && (
              <button
                onClick={() => handleDelete(paper.doi)}
                className="paper-delete-btn"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
