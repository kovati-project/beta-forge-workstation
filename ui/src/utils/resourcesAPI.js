// Resources API utilities

export async function getModels() {
  try {
    const response = await fetch('/api/models');
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error('Failed to fetch models:', error);
    return [];
  }
}

export async function deleteModel(name) {
  try {
    const response = await fetch(`/api/models/${name}`, { method: 'DELETE' });
    if (response.ok) return await response.json();
    throw new Error('Failed to delete model');
  } catch (error) {
    console.error('Failed to delete model:', error);
    throw error;
  }
}

export async function pullModel(name) {
  try {
    const response = await fetch('/api/models/pull', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to pull model');
  } catch (error) {
    console.error('Failed to pull model:', error);
    throw error;
  }
}

export async function loadLoRA(path, baseModel) {
  try {
    const response = await fetch('/api/models/load-lora', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, base_model: baseModel }),
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to load LoRA');
  } catch (error) {
    console.error('Failed to load LoRA:', error);
    throw error;
  }
}

export async function getVllmLocalModels() {
  try {
    const response = await fetch('/api/models/vllm/local');
    if (response.ok) return await response.json();
    return { models: [], slots: {} };
  } catch (error) {
    console.error('Failed to fetch vLLM local models:', error);
    return { models: [], slots: {} };
  }
}

export async function activateVllmModel(slot, model) {
  const response = await fetch('/api/models/vllm/activate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slot, model }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to activate model');
  }
  return response.json();
}

export async function downloadVllmModel(repoId, localName) {
  const response = await fetch('/api/models/vllm/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_id: repoId, local_name: localName }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to start download');
  }
  return response.json();
}

export async function getVllmDownloadStatus() {
  try {
    const response = await fetch('/api/models/vllm/download/status');
    if (response.ok) return await response.json();
    return {};
  } catch (error) {
    console.error('Failed to fetch download status:', error);
    return {};
  }
}

export async function getStorageBuckets(bucket) {
  try {
    const response = await fetch(`/api/storage/buckets/${bucket}`);
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error(`Failed to fetch ${bucket} bucket:`, error);
    return [];
  }
}

export async function getStoragePreview(path, lines = 5) {
  try {
    const response = await fetch(
      `/api/storage/preview?path=${encodeURIComponent(path)}&n=${lines}`
    );
    if (response.ok) return await response.json();
    return null;
  } catch (error) {
    console.error('Failed to get preview:', error);
    return null;
  }
}

export async function deleteStorageFile(path) {
  try {
    const response = await fetch(`/api/storage/file?path=${encodeURIComponent(path)}`, {
      method: 'DELETE',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to delete file');
  } catch (error) {
    console.error('Failed to delete file:', error);
    throw error;
  }
}

export async function getVectorCollections() {
  try {
    const response = await fetch('/api/vectors/collections');
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error('Failed to fetch vector collections:', error);
    return [];
  }
}

export async function deleteVectorCollection(name) {
  try {
    const response = await fetch(`/api/vectors/collections/${name}`, { method: 'DELETE' });
    if (response.ok) return await response.json();
    throw new Error('Failed to delete collection');
  } catch (error) {
    console.error('Failed to delete collection:', error);
    throw error;
  }
}

export async function reEmbedCollection(name) {
  try {
    const response = await fetch('/api/vectors/re-embed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ collection: name }),
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to re-embed collection');
  } catch (error) {
    console.error('Failed to re-embed collection:', error);
    throw error;
  }
}

export async function getStorageSummary() {
  try {
    const response = await fetch('/api/storage/summary');
    if (response.ok) return await response.json();
    return null;
  } catch (error) {
    console.error('Failed to fetch storage summary:', error);
    return null;
  }
}

export async function getBackupHistory() {
  try {
    const response = await fetch('/api/backup/history');
    if (response.ok) return await response.json();
    return [];
  } catch (error) {
    console.error('Failed to fetch backup history:', error);
    return [];
  }
}

export async function runBackupNow() {
  try {
    const response = await fetch('/api/backup/run', { method: 'POST' });
    if (response.ok) return await response.json();
    throw new Error('Failed to start backup');
  } catch (error) {
    console.error('Failed to start backup:', error);
    throw error;
  }
}
