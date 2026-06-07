import { useState, useEffect } from 'react';
import { getStackImages, updateAllServices, rollbackService } from '../utils/settingsAPI';
import './StackManagementSection.css';

export function StackManagementSection({ isAppliance }) {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [updateProgress, setUpdateProgress] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadImages = async () => {
      const data = await getStackImages();
      setImages(data.images || []);
      setLoading(false);
    };
    loadImages();
  }, []);

  const handleUpdateAll = async () => {
    if (!window.confirm('Pull latest images and restart all services? Brief downtime.')) return;

    setUpdating(true);
    setUpdateProgress('Starting update process...');
    setError(null);

    try {
      const response = await updateAllServices();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        setUpdateProgress((prev) => prev + chunk);
      }

      // Reload images after update
      const data = await getStackImages();
      setImages(data.images || []);
    } catch (err) {
      setError(`Update failed: ${err.message}`);
    } finally {
      setUpdating(false);
    }
  };

  const handleRollback = async (serviceName) => {
    if (!window.confirm(`Roll back ${serviceName}?`)) return;

    try {
      await rollbackService(serviceName);
      const data = await getStackImages();
      setImages(data.images || []);
    } catch (err) {
      setError(`Rollback failed: ${err.message}`);
    }
  };

  if (loading) {
    return <div className="stack-section loading">Loading stack images...</div>;
  }

  const truncateDigest = (digest) => {
    if (!digest) return '—';
    return `${digest.substring(0, 8)}...${digest.substring(digest.length - 4)}`;
  };

  if (isAppliance) {
    return (
      <div className="stack-section appliance">
        <p>Updates managed via validated stack snapshots. Contact your administrator.</p>
      </div>
    );
  }

  return (
    <div className="stack-section">
      {error && <div className="error-banner">{error}</div>}

      <button
        className="update-all-btn"
        onClick={handleUpdateAll}
        disabled={updating}
      >
        {updating ? '⟳ Updating all services...' : 'Update All Services'}
      </button>

      {updating && (
        <div className="update-progress">
          <pre>{updateProgress}</pre>
        </div>
      )}

      <table className="stack-table">
        <thead>
          <tr>
            <th>Service</th>
            <th>Image</th>
            <th>Digest</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {images.length === 0 ? (
            <tr>
              <td colSpan="4" className="empty">
                No images
              </td>
            </tr>
          ) : (
            images.map((image) => (
              <tr key={image.service}>
                <td className="service-name">{image.service}</td>
                <td className="image-name">{image.image}</td>
                <td className="digest" title={image.digest}>
                  {truncateDigest(image.digest)}
                </td>
                <td className="actions">
                  {image.previous_digest && (
                    <button
                      className="rollback-btn"
                      onClick={() => handleRollback(image.service)}
                      title="Rollback to previous digest"
                    >
                      RB
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
