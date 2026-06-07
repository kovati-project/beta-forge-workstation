import { useState, useEffect } from 'react';
import { getStorageBuckets, getStoragePreview, deleteStorageFile } from '../utils/resourcesAPI';
import { Btn } from './Btn';
import './DatasetsTab.css';

export function DatasetsTab() {
  const [files, setFiles] = useState({ raw: [], formatted: [], images: [] });
  const [loading, setLoading] = useState(true);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [previewFile, setPreviewFile] = useState(null);

  useEffect(() => {
    loadDatasets();
  }, []);

  const loadDatasets = async () => {
    setLoading(true);
    const data = await getStorageBuckets('training');
    setFiles({
      raw: data.raw || [],
      formatted: data.formatted || [],
      images: data.images || [],
    });
    setLoading(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    await uploadFiles(files);
  };

  const uploadFiles = async (fileList) => {
    setUploading(true);
    setUploadError(null);

    for (const file of fileList) {
      try {
        const formData = new FormData();
        formData.append('file', file);

        // Determine path based on file type
        let path = 'text/formatted/';
        if (file.name.endsWith('.zip')) {
          path = 'images/';
        }

        formData.append('path', path);

        const response = await fetch('/api/storage/upload', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) throw new Error('Upload failed');
      } catch (error) {
        setUploadError(error.message);
      }
    }

    setUploading(false);
    await loadDatasets();
  };

  const handlePreview = async (filePath) => {
    const data = await getStoragePreview(filePath, 5);
    if (data) {
      setPreviewData(data);
      setPreviewFile(filePath);
    }
  };

  const handleDelete = async (filePath) => {
    if (!confirm(`Delete "${filePath}"?`)) return;

    try {
      await deleteStorageFile(filePath);
      await loadDatasets();
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  return (
    <div className="datasets-tab">
      <div className="upload-zone" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
        <div className={dragOver ? 'zone-content active' : 'zone-content'}>
          {uploading ? (
            <>
              <p>Uploading...</p>
              <div className="spinner" />
            </>
          ) : (
            <p>Drop .jsonl or .zip files here</p>
          )}
        </div>
      </div>

      {uploadError && <div className="error-message">{uploadError}</div>}

      {loading ? (
        <div className="loading">Loading datasets...</div>
      ) : (
        <div className="file-sections">
          <FileSection title="text/formatted/" files={files.formatted} onPreview={handlePreview} onDelete={handleDelete} />
          <FileSection title="text/raw/" files={files.raw} onPreview={handlePreview} onDelete={handleDelete} />
          <FileSection title="images/" files={files.images} onPreview={handlePreview} onDelete={handleDelete} />
        </div>
      )}

      {previewData && (
        <div className="preview-modal" onClick={() => setPreviewData(null)}>
          <div className="preview-content" onClick={(e) => e.stopPropagation()}>
            <div className="preview-header">
              <h3>{previewFile}</h3>
              <button className="close-btn" onClick={() => setPreviewData(null)}>
                ✕
              </button>
            </div>
            <div className="preview-table">
              <table>
                <thead>
                  <tr>
                    {previewData.columns?.map((col) => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewData.lines?.map((line, idx) => (
                    <tr key={idx}>
                      {previewData.columns?.map((col) => (
                        <td key={col}>{line[col] || '—'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FileSection({ title, files, onPreview, onDelete }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="file-section">
      <button className="section-header" onClick={() => setExpanded(!expanded)}>
        <span>{expanded ? '▾' : '▸'}</span>
        <span>{title}</span>
        <span className="file-count">({files.length})</span>
      </button>

      {expanded && (
        <table className="files-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Size</th>
              <th>Modified</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {files.length === 0 ? (
              <tr>
                <td colSpan="4" className="empty">
                  No files
                </td>
              </tr>
            ) : (
              files.map((file) => (
                <tr key={file.path}>
                  <td>{file.name}</td>
                  <td>{file.size}</td>
                  <td>{file.modified}</td>
                  <td>
                    <button className="action-btn" onClick={() => onPreview(file.path)} title="Preview">
                      👁
                    </button>
                    <button className="action-btn" onClick={() => onDelete(file.path)} title="Delete">
                      ✕
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
