import { useState, useEffect } from 'react';
import { getServices } from '../utils/exposeAPI';
import { DotStatus } from './DotStatus';
import { Tag } from './Tag';
import './OpenAIEndpointsSection.css';

const OPENAI_ENDPOINTS = [
  { name: 'vllm-pair-a', port: 8000, path: '/v1' },
  { name: 'ollama', port: 11434, path: '/v1' },
  { name: 'vllm-pair-b', port: 8001, path: '/v1' },
  { name: 'vllm-4gpu', port: 8002, path: '/v1' },
  { name: 'whisper-stt', port: 9099, path: '/v1/audio' },
  { name: 'piper-tts', port: 5000, path: '/v1/audio/speech' },
];

export function OpenAIEndpointsSection() {
  const [services, setServices] = useState({});
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(null);

  useEffect(() => {
    loadServices();
  }, []);

  const loadServices = async () => {
    setLoading(true);
    const data = await getServices();
    const serviceMap = {};
    data.forEach((svc) => {
      serviceMap[svc.name] = svc;
    });
    setServices(serviceMap);
    setLoading(false);
  };

  const getURL = (endpoint) => {
    const host = window.location.hostname;
    return `http://${host}:${endpoint.port}${endpoint.path}`;
  };

  const handleCopy = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
      setTimeout(() => setCopied(null), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  return (
    <div className="openai-section">
      {loading ? (
        <div className="loading">Loading endpoints...</div>
      ) : (
        <table className="endpoints-table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Base URL</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {OPENAI_ENDPOINTS.map((endpoint) => {
              const svc = services[endpoint.name];
              const url = getURL(endpoint);
              const isRunning = svc?.status === 'running';

              return (
                <tr key={endpoint.name}>
                  <td className="service-name">{endpoint.name}</td>
                  <td className="url-cell">{url}</td>
                  <td className="status-cell">
                    <div className="status-indicator">
                      <DotStatus status={isRunning ? 'running' : 'stopped'} />
                      <Tag variant={isRunning ? 'green' : 'gray'}>
                        {isRunning ? 'running' : 'stopped'}
                      </Tag>
                    </div>
                  </td>
                  <td>
                    <button
                      className="copy-btn"
                      onClick={() => handleCopy(url)}
                      title="Copy URL"
                    >
                      {copied === url ? '✓ copied' : '📋'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
