import { useState, useEffect } from 'react';
import { getStorageBuckets, loadLoRA } from '../utils/resourcesAPI';
import { Btn } from './Btn';
import './CheckpointsTab.css';

export function CheckpointsTab() {
  const [checkpoints, setCheckpoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    loadCheckpoints();
  }, []);

  const loadCheckpoints = async () => {
    setLoading(true);
    const data = await getStorageBuckets('checkpoints');
    // Group by run name
    const grouped = {};
    (data.runs || []).forEach((run) => {
      grouped[run.name] = run;
    });
    setCheckpoints(Object.entries(grouped));
    setLoading(false);
  };

  const toggleExpanded = (name) => {
    setExpanded((prev) => ({
      ...prev,
      [name]: !prev[name],
    }));
  };

  const handleLoad = async (path, baseModel, type) => {
    try {
      await loadLoRA(path, baseModel);
      alert(`Loaded ${type === 'text' ? 'text LoRA' : 'image LoRA'}`);
    } catch (error) {
      alert(`Failed to load: ${error.message}`);
    }
  };

  return (
    <div className="checkpoints-tab">
      {loading ? (
        <div className="loading">Loading checkpoints...</div>
      ) : checkpoints.length === 0 ? (
        <div className="empty">No checkpoints available</div>
      ) : (
        <div className="checkpoint-groups">
          {checkpoints.map(([runName, run]) => (
            <div key={runName} className="checkpoint-group">
              <button className="group-header" onClick={() => toggleExpanded(runName)}>
                <span>{expanded[runName] ? '▾' : '▸'}</span>
                <span className="group-name">{runName}</span>
                <span className="group-type">({run.type})</span>
                <span className="group-date">{run.date}</span>
              </button>

              {expanded[runName] && (
                <div className="group-files">
                  {run.files?.map((file) => (
                    <div key={file.path} className="checkpoint-file">
                      <div className="file-info">
                        <div className="file-name">{file.name}</div>
                        <div className="file-size">{file.size}</div>
                      </div>
                      <div className="file-actions">
                        {file.type === 'checkpoint' && (
                          <Btn
                            label="Load"
                            onClick={() =>
                              handleLoad(
                                file.path,
                                run.base_model,
                                run.type === 'text' ? 'text' : 'image'
                              )
                            }
                            size="sm"
                          />
                        )}
                        {file.type === 'config' && (
                          <button className="view-btn" title="View config">
                            View
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
