import { Panel } from '../components/Panel';
import { OpenAIEndpointsSection } from '../components/OpenAIEndpointsSection';
import { MCPServersSection } from '../components/MCPServersSection';
import { APIKeysSection } from '../components/APIKeysSection';
import { ExternalAccessSection } from '../components/ExternalAccessSection';
import './Expose.css';

export function Expose() {
  return (
    <div className="expose-page">
      <div className="page-header">
        <h1>Expose</h1>
      </div>

      <Panel title="OpenAI-Compatible Endpoints">
        <OpenAIEndpointsSection />
      </Panel>

      <Panel title="MCP Servers">
        <MCPServersSection />
      </Panel>

      <Panel title="API Keys">
        <APIKeysSection />
      </Panel>

      <Panel title="External Access">
        <ExternalAccessSection />
      </Panel>
    </div>
  );
}
