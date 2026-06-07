// Monitor API utilities

export async function getGPUMetrics() {
  try {
    const response = await fetch('/api/metrics/gpu');
    if (response.ok) return await response.json();
    return {};
  } catch (error) {
    console.error('Failed to fetch GPU metrics:', error);
    return {};
  }
}

export async function getSystemMetrics() {
  try {
    const response = await fetch('/api/metrics/system');
    if (response.ok) return await response.json();
    return {};
  } catch (error) {
    console.error('Failed to fetch system metrics:', error);
    return {};
  }
}

export async function getContainerMetrics() {
  try {
    const response = await fetch('/api/metrics/containers');
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error('Failed to fetch container metrics:', error);
    return [];
  }
}

export async function getTraces(params = {}) {
  try {
    const query = new URLSearchParams(params).toString();
    const response = await fetch(`/api/traces?${query}`);
    if (response.ok) return await response.json();
    return { traces: [] };
  } catch (error) {
    console.error('Failed to fetch traces:', error);
    return { traces: [] };
  }
}

export async function getInitialLogs(serviceName, lines = 200) {
  try {
    const response = await fetch(
      `/api/services/${serviceName}/logs?n=${lines}`
    );
    if (response.ok) return await response.json();
    return { lines: [] };
  } catch (error) {
    console.error('Failed to fetch logs:', error);
    return { lines: [] };
  }
}

export async function getAlerts() {
  try {
    const response = await fetch('/api/alerts');
    if (response.ok) return await response.json();
    return { active: [], total: 0 };
  } catch (error) {
    console.error('Failed to fetch alerts:', error);
    return { active: [], total: 0 };
  }
}

export async function getAlertHistory() {
  try {
    const response = await fetch('/api/alerts/history');
    if (response.ok) return await response.json();
    return { alerts: [] };
  } catch (error) {
    console.error('Failed to fetch alert history:', error);
    return { alerts: [] };
  }
}
