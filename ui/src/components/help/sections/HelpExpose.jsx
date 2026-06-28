import { Panel } from '../../Panel';

export function HelpExpose() {
  const endpoints = [
    { service: 'vLLM (pair-a)', port: '8000', path: '/v1', desc: 'Primary LLM inference (34B–40B models via GPU 0+3)' },
    { service: 'vLLM (pair-b)', port: '8001', path: '/v1', desc: 'Secondary LLM inference stack (GPU 1+2)' },
    { service: 'vLLM (4-GPU)', port: '8002', path: '/v1', desc: '70B+ model inference (all 4 GPUs)' },
    { service: 'Ollama', port: '11434', path: '/v1', desc: 'GGUF model inference, simpler setup' },
    { service: 'Whisper STT', port: '9099', path: '/v1/audio/transcriptions', desc: 'Speech-to-text (audio → text)' },
    { service: 'Piper TTS', port: '5000', path: '/v1/audio/speech', desc: 'Text-to-speech (text → audio)' },
  ];

  const mcpServers = [
    { name: 'mcp-filesystem', port: '3100', desc: 'Read and write files in the /data/ directory tree on the workstation.' },
    { name: 'mcp-browser', port: '3101', desc: 'Headless browser control via Playwright. Enables web scraping and automation.' },
    { name: 'mcp-code-exec', port: '3102', desc: 'Sandboxed Python and shell execution environment.' },
    { name: 'mcp-fetch', port: '3103', desc: 'HTTP fetch and web scraping tool.' },
  ];

  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Expose</h2>
        <p className="help-section-subtitle">
          The Expose page manages how Kovati OS makes its services available to external clients: AI tools, API consumers, and MCP-compatible agents.
        </p>
      </div>

      <Panel title="OpenAI-Compatible Endpoints">
        <div className="help-body">
          <p>All inference services expose an OpenAI-compatible <span className="help-code">/v1</span> API. Any client that supports the OpenAI SDK can connect — just change the base URL and (optionally) the API key.</p>
          <table className="help-table" style={{marginTop: 8}}>
            <thead>
              <tr>
                <th>Service</th>
                <th>Port</th>
                <th>Path</th>
                <th>Use</th>
              </tr>
            </thead>
            <tbody>
              {endpoints.map((e) => (
                <tr key={e.service}>
                  <td><strong>{e.service}</strong></td>
                  <td><span className="help-code">{e.port}</span></td>
                  <td><span className="help-code">{e.path}</span></td>
                  <td>{e.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="help-tip" style={{marginTop: 10}}>
            <strong>How to connect:</strong> Click the copy icon next to any endpoint to copy its full URL (<span className="help-code">http://&lt;ip&gt;:&lt;port&gt;/v1</span>). Paste this as the <span className="help-code">base_url</span> in your client. The status indicator shows whether the service is currently running.
          </div>
        </div>
      </Panel>

      <Panel title="MCP Servers">
        <div className="help-body">
          <p>Model Context Protocol (MCP) servers extend AI agents with tool capabilities — file access, web browsing, code execution, and HTTP fetching.</p>
          <table className="help-table" style={{marginTop: 8}}>
            <thead>
              <tr>
                <th>Server</th>
                <th>Port</th>
                <th>Capability</th>
              </tr>
            </thead>
            <tbody>
              {mcpServers.map((s) => (
                <tr key={s.name}>
                  <td><span className="help-code">{s.name}</span></td>
                  <td><span className="help-code">{s.port}</span></td>
                  <td>{s.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3 style={{marginTop: 12}}>Adding an MCP server to Claude Desktop</h3>
          <ol className="help-steps" style={{marginTop: 6}}>
            <li className="help-step">
              <span className="help-step-number">1</span>
              <div className="help-step-body">Ensure the MCP server is running (start it from the Tools page if needed).</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">2</span>
              <div className="help-step-body">Click <strong>Test Connection</strong> to verify the server is reachable.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">3</span>
              <div className="help-step-body">Click <strong>Export Config</strong> to download a pre-filled <span className="help-code">claude_desktop_config.json</span> snippet.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">4</span>
              <div className="help-step-body">Merge the snippet into your Claude Desktop configuration file and restart Claude Desktop.</div>
            </li>
          </ol>
        </div>
      </Panel>

      <Panel title="API Keys">
        <div className="help-body">
          <p>API keys protect programmatic access to the Kovati API and inference endpoints.</p>
          <h3>Generating a key</h3>
          <ol className="help-steps" style={{marginTop: 6}}>
            <li className="help-step">
              <span className="help-step-number">1</span>
              <div className="help-step-body">Enter a descriptive name for the key (e.g., <span className="help-code">cursor-integration</span>).</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">2</span>
              <div className="help-step-body">Click <strong>Generate</strong>. The key is displayed once — copy it immediately. It will not be shown again.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">3</span>
              <div className="help-step-body">The key appears in the active keys list with its creation date and last-used timestamp.</div>
            </li>
          </ol>
          <div className="help-warn" style={{marginTop: 8}}>
            <strong>Important:</strong> If you lose a key, you must delete it and generate a new one. There is no way to retrieve the full key value after the initial reveal.
          </div>
        </div>
      </Panel>

      <Panel title="External Access">
        <div className="help-body">
          <p>Controls which services are accessible from outside the local network via the Caddy reverse proxy:</p>
          <ul>
            <li><strong>Enable Caddy</strong> — toggle the reverse proxy on or off</li>
            <li><strong>Public routing</strong> — expose specific services at a public domain</li>
            <li><strong>TLS</strong> — Caddy automatically provisions and renews Let's Encrypt certificates</li>
            <li><strong>IP whitelist</strong> — restrict external access to specific IP ranges</li>
          </ul>
          <div className="help-warn">
            <strong>Security note:</strong> Only expose services that require external access. Always use TLS and an API key or Authentik authentication when exposing inference endpoints publicly.
          </div>
        </div>
      </Panel>
    </div>
  );
}
