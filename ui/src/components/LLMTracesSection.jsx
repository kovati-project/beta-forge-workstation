import { useState, useEffect } from 'react';
import { getTraces } from '../utils/monitorAPI';
import { Tag } from './Tag';
import './LLMTracesSection.css';

export function LLMTracesSection() {
  const [traces, setTraces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [revealedId, setRevealedId] = useState(null);
  const [filters, setFilters] = useState({
    model: '',
    latency_min: 0,
  });

  useEffect(() => {
    loadTraces();
  }, [filters]);

  const loadTraces = async () => {
    setLoading(true);
    const data = await getTraces(filters);
    setTraces(data.traces || []);
    setLoading(false);
  };

  const getLatencyColor = (latency) => {
    if (latency < 2) return '--cyan';
    if (latency < 5) return '--amber';
    return '--red';
  };

  const handleToggleReveal = (id) => {
    setRevealedId(revealedId === id ? null : id);
  };

  return (
    <div className="llm-traces-section">
      <div className="section-header">
        <h3>LLM Traces</h3>
        <span className="source">Langfuse :3002</span>
        <div className="filter-controls">
          <input
            type="text"
            placeholder="Model filter..."
            className="filter-input"
            onChange={(e) =>
              setFilters((p) => ({ ...p, model: e.target.value }))
            }
          />
          <input
            type="number"
            placeholder="Min latency (s)"
            className="filter-input"
            onChange={(e) =>
              setFilters((p) => ({
                ...p,
                latency_min: parseFloat(e.target.value) || 0,
              }))
            }
          />
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading traces...</div>
      ) : traces.length === 0 ? (
        <div className="empty">No traces found</div>
      ) : (
        <div className="traces-list">
          {traces.map((trace) => {
            const latencyColor = getLatencyColor(trace.latency);
            const isExpanded = expandedId === trace.id;
            const isRevealed = revealedId === trace.id;

            return (
              <div key={trace.id} className="trace-item">
                <button
                  className={`trace-row ${isExpanded ? 'expanded' : ''}`}
                  onClick={() =>
                    setExpandedId(isExpanded ? null : trace.id)
                  }
                >
                  <span className="toggle">{isExpanded ? '▾' : '▸'}</span>
                  <span className="time">{trace.time}</span>
                  <span className="model">{trace.model}</span>
                  <span className="tokens">
                    {trace.prompt_tokens?.toLocaleString()}
                  </span>
                  <span className="tokens">
                    {trace.completion_tokens?.toLocaleString()}
                  </span>
                  <span className={`latency latency-${latencyColor.slice(2)}`}>
                    {trace.latency.toFixed(2)}s
                    {trace.latency > 5 ? ' ⚠' : ''}
                  </span>
                  <span className="score">{trace.score || '—'}</span>
                </button>

                {isExpanded && (
                  <div className="trace-details">
                    <div className="detail-row">
                      <span className="detail-label">Prompt:</span>
                      <span className={`detail-value ${isRevealed ? 'revealed' : 'redacted'}`}>
                        {isRevealed
                          ? trace.prompt
                          : '██████████████████ (click to reveal)'}
                      </span>
                      <button
                        className="reveal-btn"
                        onClick={() => handleToggleReveal(trace.id)}
                      >
                        {isRevealed ? 'Redact' : 'Reveal'}
                      </button>
                    </div>

                    <div className="detail-row">
                      <span className="detail-label">Completion:</span>
                      <span className={`detail-value ${isRevealed ? 'revealed' : 'redacted'}`}>
                        {isRevealed
                          ? trace.completion
                          : '██████████████████'}
                      </span>
                    </div>

                    {trace.metadata && (
                      <div className="detail-row">
                        <span className="detail-label">Metadata:</span>
                        <span className="detail-value">
                          {Object.entries(trace.metadata)
                            .map(([k, v]) => `${k}=${v}`)
                            .join(' · ')}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="pagination">
        Showing {traces.length} traces
      </div>
    </div>
  );
}
