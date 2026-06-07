import { useState, useEffect } from 'react';
import { Btn } from './Btn';
import './TextLoRA1Dataset.css';

export function TextLoRA1Dataset({ onNext, initialValue }) {
  const [mode, setMode] = useState('browse');
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(initialValue?.path || null);
  const [preview, setPreview] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (mode === 'browse') {
      loadFiles();
    }
  }, [mode]);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/storage/list?path=/data/training/text/formatted');
      if (response.ok) {
        const data = await response.json();
        setFiles(data.files || []);
      }
    } catch (err) {
      setError('Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = async (file) => {
    setSelected(file.path);
    setError(null);
    
    // Fetch preview
    try {
      const response = await fetch(
        `/api/storage/preview?path=${encodeURIComponent(file.path)}&n=3`
      );
      if (response.ok) {
        const data = await response.json();
        setPreview(data.lines || []);
      }
    } catch (err) {
      setError('Failed to load preview');
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate JSONL
    const text = await file.text();
    const lines = text.split('\n').filter((l) => l.trim());
    
    const previewLines = [];
    const errors = [];

    for (let i = 0; i < Math.min(3, lines.length); i++) {
      try {
        const obj = JSON.parse(lines[i]);
        if (!obj.instruction || !obj.input || !obj.output) {
          errors.push(`Line ${i + 1}: missing required fields`);
        }
        previewLines.push(
          `"${obj.instruction.substring(0, 40)}..." | "${obj.input.substring(0, 20)}..." | "${obj.output.substring(0, 20)}..."`
        );
      } catch (err) {
        errors.push(`Line ${i + 1}: ${err.message}`);
      }
    }

    if (errors.length > 0) {
      setError(errors[0]);
      return;
    }

    setSelected(file.name);
    setPreview(previewLines);
    setError(null);
  };

  const canNext = !!selected;

  return (
    <div className="text-lora-dataset">
      <div className="dataset-header">DATASET SOURCE</div>

      <div className="dataset-mode-tabs">
        <button
          className={`mode-tab ${mode === 'upload' ? 'active' : ''}`}
          onClick={() => setMode('upload')}
        >
          ○ Upload .jsonl file
        </button>
        <button
          className={`mode-tab ${mode === 'browse' ? 'active' : ''}`}
          onClick={() => setMode('browse')}
        >
          ● Browse MinIO /data/training/text/formatted/
        </button>
      </div>

      {mode === 'upload' ? (
        <div className="upload-zone">
          <label className="upload-input">
            <input type="file" accept=".jsonl" onChange={handleUpload} />
            Click to select or drag & drop .jsonl file
          </label>
        </div>
      ) : (
        <div className="browse-list">
          {loading ? (
            <div className="loading">Loading files...</div>
          ) : files.length === 0 ? (
            <div className="empty">No files found in /data/training/text/formatted/</div>
          ) : (
            <table className="files-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Records</th>
                  <th>Modified</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => (
                  <tr
                    key={file.path}
                    className={`file-row ${selected === file.path ? 'selected' : ''}`}
                    onClick={() => handleFileSelect(file)}
                  >
                    <td>{file.name}</td>
                    <td>{file.records?.toLocaleString() || '—'}</td>
                    <td>{file.modified || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {preview.length > 0 && (
        <div className="preview-section">
          <div className="preview-header">FORMAT PREVIEW (first 3 rows):</div>
          <div className="preview-table">
            <div className="preview-header-row">instruction | input | output</div>
            {preview.map((line, idx) => (
              <div key={idx} className="preview-row">{line}</div>
            ))}
          </div>
        </div>
      )}

      <div className="button-row">
        <Btn
          variant="cyan"
          size="sm"
          onClick={() => onNext({ path: selected })}
          disabled={!canNext}
        >
          Next →
        </Btn>
      </div>
    </div>
  );
}
