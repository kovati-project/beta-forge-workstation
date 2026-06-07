import { useState, useEffect } from 'react';
import { getVectorCollections, deleteVectorCollection, reEmbedCollection } from '../utils/resourcesAPI';
import { VBar } from './VBar';
import './VectorsTab.css';

export function VectorsTab() {
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reEmbedding, setReEmbedding] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleteInput, setDeleteInput] = useState('');

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    setLoading(true);
    const data = await getVectorCollections();
    setCollections(data.collections || []);
    setLoading(false);
  };

  const handleReEmbed = async (name) => {
    setReEmbedding(name);
    try {
      await reEmbedCollection(name);
      await loadCollections();
    } catch (error) {
      alert(`Re-embed failed: ${error.message}`);
    } finally {
      setReEmbedding(null);
    }
  };

  const handleDeleteClick = (name) => {
    setDeleteConfirm(name);
    setDeleteInput('');
  };

  const handleConfirmDelete = async () => {
    if (deleteInput !== deleteConfirm) {
      alert('Name does not match');
      return;
    }

    try {
      await deleteVectorCollection(deleteConfirm);
      await loadCollections();
      setDeleteConfirm(null);
    } catch (error) {
      alert(`Delete failed: ${error.message}`);
    }
  };

  return (
    <div className="vectors-tab">
      {loading ? (
        <div className="loading">Loading collections...</div>
      ) : collections.length === 0 ? (
        <div className="empty">No vector collections</div>
      ) : (
        <table className="vectors-table">
          <thead>
            <tr>
              <th>Collection</th>
              <th>Vectors</th>
              <th>Dimension</th>
              <th>Disk Size</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {collections.map((coll) => (
              <tr key={coll.name}>
                <td className="collection-name">{coll.name}</td>
                <td>{(coll.count || 0).toLocaleString()}</td>
                <td>{coll.dimension}</td>
                <td>{coll.size}</td>
                <td className="actions">
                  <button
                    className="action-btn"
                    onClick={() => handleReEmbed(coll.name)}
                    disabled={reEmbedding === coll.name}
                    title="Re-embed collection"
                  >
                    {reEmbedding === coll.name ? '⟳' : '↻'}
                  </button>
                  <button
                    className="action-btn delete"
                    onClick={() => handleDeleteClick(coll.name)}
                    title="Delete collection"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {deleteConfirm && (
        <div className="delete-modal" onClick={() => setDeleteConfirm(null)}>
          <div className="delete-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm Delete</h3>
            <p>Type the collection name to confirm deletion:</p>
            <p className="confirm-name">{deleteConfirm}</p>
            <input
              type="text"
              placeholder="Enter collection name"
              value={deleteInput}
              onChange={(e) => setDeleteInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleConfirmDelete()}
            />
            <div className="dialog-buttons">
              <button className="btn-cancel" onClick={() => setDeleteConfirm(null)}>
                Cancel
              </button>
              <button
                className="btn-delete"
                onClick={handleConfirmDelete}
                disabled={deleteInput !== deleteConfirm}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
