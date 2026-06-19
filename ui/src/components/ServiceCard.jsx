import React, { useState, useEffect, useRef } from 'react';
import { Btn } from './Btn';
import { Toggle } from './Toggle';
import { DotStatus } from './DotStatus';
import { Tag } from './Tag';
import { getServiceUrl } from '../utils/serviceRegistry';
import { ALWAYS_ON_SERVICES, BATCH_SERVICES } from '../data/servicesMock';
import './ServiceCard.css';

function ServiceCardExpanded({ service, serviceName }) {
  const [logs, setLogs] = useState(null);
  const [logsError, setLogsError] = useState(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await fetch(`/api/services/${serviceName}/logs?n=100`);
        if (response.ok) {
          const data = await response.json();
          setLogs(data.logs || []);
        }
      } catch (error) {
        setLogsError('Failed to load logs');
      }
    };

    fetchLogs();
  }, [serviceName]);

  const formatUptime = (seconds) => {
    if (!seconds) return '—';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  return (
    <div className="service-card-expanded">
      <div className="expanded-row">
        <span className="expanded-label">Image:</span>
        <span className="expanded-value">{service.image || '—'}</span>
      </div>

      <div className="expanded-row">
        <span className="expanded-label">Uptime:</span>
        <span className="expanded-value">{formatUptime(service.uptime_seconds)}</span>
      </div>

      <div className="expanded-row">
        <span className="expanded-label">CPU:</span>
        <span className="expanded-value">
          {(service.cpu_pct || 0).toFixed(1)}%
          {service.mem_gb && ` · Memory: ${service.mem_gb.toFixed(1)} GB`}
        </span>
      </div>

      <div className="expanded-logs">
        <div className="expanded-logs-header">Recent logs:</div>
        {logsError ? (
          <div className="logs-error">{logsError}</div>
        ) : logs && logs.length > 0 ? (
          <div className="logs-content">
            {logs.map((line, idx) => (
              <div key={idx} className="log-line">
                {line}
              </div>
            ))}
          </div>
        ) : (
          <div className="logs-empty">No logs available</div>
        )}
      </div>
    </div>
  );
}

function ServiceCardInner({
  serviceName,
  service,
  onToggleService,
  isManaged,
  onFocus,
}) {
  const [expanded, setExpanded] = useState(false);
  const [toggling, setToggling] = useState(false);
  const cardRef = useRef(null);
  const isAlwaysOn = ALWAYS_ON_SERVICES.has(serviceName);
  const isBatch = BATCH_SERVICES.has(serviceName);

  // Handle focus from dashboard click
  useEffect(() => {
    if (onFocus) {
      onFocus(cardRef.current);
    }
  }, [onFocus]);

  // Auto-expand if focused
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const focus = urlParams.get('focus');
    if (focus === serviceName) {
      setExpanded(true);
    }
  }, [serviceName]);

  const handleToggle = async (checked) => {
    setToggling(true);
    try {
      await onToggleService(serviceName, checked);
    } finally {
      setToggling(false);
    }
  };

  const handleOpen = () => {
    const url = getServiceUrl(serviceName);
    if (url) window.open(url, '_blank');
  };

  const getStatusColor = (status) => {
    if (status === 'running') return 'green';
    if (status === 'starting' || status === 'degraded') return 'amber';
    if (status === 'error' || status === 'stopped') return 'red';
    return 'gray';
  };

  const getStatusLabel = (status) => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  return (
    <div
      className={`service-card ${expanded ? 'expanded' : ''} ${isManaged ? 'managed' : ''}`}
      id={`svc-${serviceName}`}
      ref={cardRef}
    >
      <div className="service-card-row">
        <DotStatus status={getStatusColor(service.status)} />

        <span className="service-name">{serviceName}</span>

        {service.port && (
          <span className="service-port">:{service.port}</span>
        )}

        {service.gpus && service.gpus.length > 0 && (
          <div className="service-gpu-tags">
            {service.gpus.map((gpu) => (
              <Tag key={gpu} variant="cyan">
                GPU{gpu}
              </Tag>
            ))}
          </div>
        )}

        <Tag variant={getStatusColor(service.status)}>
          {getStatusLabel(service.status)}
        </Tag>

        <Btn variant="gray" size="sm" onClick={handleOpen}>
          Open ↗
        </Btn>

        {isAlwaysOn ? (
          <span
            className="service-badge-system"
            title="System service — managed independently of loadout profiles"
          >
            SYSTEM
          </span>
        ) : isBatch ? (
          <span
            className="service-badge-batch"
            title="Batch training job — launch from the Training page, not via toggle"
          >
            BATCH
          </span>
        ) : (
          <Toggle
            checked={service.status === 'running'}
            disabled={isManaged || toggling}
            onChange={handleToggle}
            title={isManaged ? `Managed by loadout ${service.managed_by_loadout}` : ''}
          />
        )}

        <button
          className="service-expand-btn"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '▾' : '▸'}
        </button>
      </div>

      {expanded && (
        <ServiceCardExpanded service={service} serviceName={serviceName} />
      )}

      {isManaged && (
        <div className="service-managed-tooltip">
          Managed by loadout {service.managed_by_loadout}
          <br />
          Switch profile to change
        </div>
      )}
    </div>
  );
}

export const ServiceCard = React.memo(ServiceCardInner);
