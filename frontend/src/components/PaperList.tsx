import React, { useState, useEffect, useRef } from 'react';
import { listPapers, uploadPaper, deletePaper, getIndexingStatus } from '../api/client';

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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{
        padding: '16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid #333',
        fontSize: '14px',
        color: '#aaa',
      }}>
        <span>Papers ({papers.length})</span>
        <button
          style={{
            padding: '6px 12px',
            background: '#e94560',
            border: 'none',
            borderRadius: '6px',
            color: 'white',
            cursor: 'pointer',
            fontSize: '12px',
          }}
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
        <p style={{ padding: '8px 16px', fontSize: '12px', color: '#4caf50', margin: 0 }}>
          {message}
        </p>
      )}

      <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
        {papers.map(paper => (
          <div
            key={paper.doi || paper.filename}
            style={{
              padding: '10px 12px',
              borderRadius: '8px',
              marginBottom: '6px',
              background: '#16213e',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '12px', color: 'white', marginBottom: '4px' }}>
                {paper.title
                  ? paper.title.substring(0, 60) + (paper.title.length > 60 ? '...' : '')
                  : paper.filename}
              </div>
              <div style={{ fontSize: '11px', color: '#888' }}>
                {paper.year && `${paper.year} · `}
                {paper.authors
                  ? paper.authors.split(';')[0].split(',')[0].trim() + ' et al.'
                  : ''}
              </div>
            </div>
            {paper.doi && (
              <button
                onClick={() => handleDelete(paper.doi)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#e94560',
                  cursor: 'pointer',
                  fontSize: '18px',
                  padding: '0 4px',
                  flexShrink: 0,
                  lineHeight: 1,
                }}
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
