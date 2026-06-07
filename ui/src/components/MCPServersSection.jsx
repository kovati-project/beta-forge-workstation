import { useState, useEffect } from 'react';
import { getServices, testMCP, toggleMCPService } from '../utils/exposeAPI';
import { DotStatus } from './DotStatus';
import { Btn } from './Btn';
import './MCPServersSection.css';

const MCP_SERVERS = [
  {
    name: 'mcp-filesystem',
    port: 3100,
    role: 'Read/write /data/ directory tree',
  },
  {
    name: 'mcp-browser',
    port: 3101,
    role: 'Playwright headless browsing',
  },
  {
    name: 'mcp-code-exec',
    port: 3102,
    role: 'Sandboxed Python/shell execution',
  },
  {
    name: 'mcp-fetch',
    port: 3103,
    role: 'HTTP fetch and web scraping',
  },
];

export function MCPServersSection() {
  const [services, setServices] = useState({});
  const [loading, setLoading] = useState(true);
  const [testResults, setTestResults] = useState({});
  const [copied, setCopied] = useState(null);
  const [toggling, setToggling] = useState(null);

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

  const getConnectionString = (server) => {
    const host = window.location.hostname;
    return JSON.stringify({
      type: 'streamable_http',
      url: `http://${host}:${server.port}/mcp`,
    });
  };

  const handleCopyConnection = async (server) => {
    try {
      const str = getConnectionString(server);
      await navigator.clipboard.writeText(str);
      setCopied(server.name);
      setTimeout(() => setCopied(null), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const handleTest = async (name) => {
    try {
      const result = await testMCP(name);
      setTestResults((prev) => ({
        ...prev,
        [name]: { success: true, message: result.message },
      }));
      setTimeout(
        () =>
          setTestResults((prev) => {
            const copy = { ...prev };
            delete copy[name];
            return copy;
          }),
        10000
      );
    } catch (error) {
      setTestResults((prev) => ({
        ...prev,
        [name]: { success: false, message: error.message },
      }));
      setTimeout(
        () =>
          setTestResults((prev) => {
            const copy = { ...prev };
            delete copy[name];
            return copy;
          }),
        10000
      );
    }
  };

  const handleToggle = async (name, currentStatus) => {
    setToggling(name);
    try {
      await toggleMCPService(name, currentStatus === 'stopped');
      await loadServices();
    } catch (error) {
      console.error('Toggle failed:', error);
    } finally {
      setToggling(null);
    }
  };

  const handleExportConfig = () => {
    const config = {
      mcpServers: {},
    };

    MCP_SERVERS.forEach((server) => {
      const svc = services[server.name];
      if (svc?.status === 'running') {
        const host = window.location.hostname;
        config.mcpServers[`kovati-${server.name.split('-').slice(1).join('-')}`] = {
          type: 'streamable_http',
          url: `http://${host}:${server.port}/mcp`,
        };
      }
    });

    const dateStr = new Date().toISOString().split('T')[0];
    const filename = `kovati-mcp-config-${dateStr}.json`;
    const blob = new Blob([JSON.stringify(config, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mcp-section">
      <div className="mcp-header">
        <span>MCP spec 2025-03 · streamable_http</span>
      </div>

      {loading ? (
        <div className="loading">Loading MCP servers...</div>
      ) : (
        <div className="mcp-cards">
          {MCP_SERVERS.map((server) => {
            const svc = services[server.name];
            const isRunning = svc?.status === 'running';
            const testResult = testResults[server.name];
            const connStr = getConnectionString(server);

            return (
              <div key={server.name} className="mcp-card">
                <div className="card-header">
                  <DotStatus status={isRunning ? 'running' : 'stopped'} />
                  <span className="card-name">{server.name}</span>
                  <span className="card-port">:{server.port}</span>
                </div>

                <div className="card-connection">
                  {connStr}
                </div>

                <div className="card-role">Role: {server.role}</div>

                {testResult && (
                  <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
                    {testResult.success ? '✓' : '✗'} {testResult.message}
                  </div>
                )}

                <div className="card-actions">
                  <button
                    className="action-btn"
                    onClick={() => handleCopyConnection(server)}
                    title="Copy connection string"
                  >
                    {copied === server.name ? '✓ Copied' : 'Copy'}
                  </button>
                  <Btn
                    label="Test"
                    onClick={() => handleTest(server.name)}
                    size="sm"
                  />
                  <button
                    className={`toggle-btn ${isRunning ? 'active' : ''}`}
                    onClick={() => handleToggle(server.name, svc?.status)}
                    disabled={toggling === server.name}
                    title={isRunning ? 'Stop' : 'Start'}
                  >
                    {isRunning ? '●' : '○'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Btn
        label="Export claude_desktop_config.json"
        onClick={handleExportConfig}
        variant="amber"
      />
    </div>
  );
}
