// Expose API utilities

export async function getServices() {
  try {
    const response = await fetch('/api/services');
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error('Failed to fetch services:', error);
    return [];
  }
}

export async function getAPIKeys() {
  try {
    const response = await fetch('/api/keys');
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error('Failed to fetch API keys:', error);
    return [];
  }
}

export async function createAPIKey(name, scope) {
  try {
    const response = await fetch('/api/keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, scope }),
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to create key');
  } catch (error) {
    console.error('Failed to create API key:', error);
    throw error;
  }
}

export async function revokeAPIKey(name) {
  try {
    const response = await fetch(`/api/keys/${name}`, { method: 'DELETE' });
    if (response.ok) return await response.json();
    throw new Error('Failed to revoke key');
  } catch (error) {
    console.error('Failed to revoke API key:', error);
    throw error;
  }
}

export async function testMCP(name) {
  try {
    const response = await fetch(`/api/mcp/${name}/test`, { method: 'POST' });
    if (response.ok) return await response.json();
    throw new Error('Connection failed');
  } catch (error) {
    console.error('MCP test failed:', error);
    throw error;
  }
}

export async function getNetworkRoutes() {
  try {
    const response = await fetch('/api/network');
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error('Failed to fetch network routes:', error);
    return [];
  }
}

export async function updateNetworkRoute(service, exposed) {
  try {
    const response = await fetch(`/api/network/routes/${service}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exposed }),
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to update route');
  } catch (error) {
    console.error('Failed to update network route:', error);
    throw error;
  }
}

export async function toggleMCPService(name, enabled) {
  try {
    const endpoint = enabled ? 'start' : 'stop';
    const response = await fetch(`/api/services/${name}/${endpoint}`, {
      method: 'POST',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to toggle service');
  } catch (error) {
    console.error('Failed to toggle MCP service:', error);
    throw error;
  }
}
