// Training API utilities

export async function getTrainingStatus() {
  try {
    const response = await fetch('/api/training/status');
    if (response.ok) {
      return await response.json();
    }
    return null;
  } catch (error) {
    console.error('Failed to fetch training status:', error);
    return null;
  }
}

export async function startTraining(config) {
  try {
    const response = await fetch('/api/training/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (response.ok) {
      return await response.json();
    }
    throw new Error('Failed to start training');
  } catch (error) {
    console.error('Failed to start training:', error);
    throw error;
  }
}

export async function stopTraining() {
  try {
    const response = await fetch('/api/training/stop', { method: 'POST' });
    if (response.ok) {
      return await response.json();
    }
    throw new Error('Failed to stop training');
  } catch (error) {
    console.error('Failed to stop training:', error);
    throw error;
  }
}

export async function exportCheckpoint(runName) {
  try {
    const response = await fetch('/api/training/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_name: runName }),
    });
    if (response.ok) {
      return await response.json();
    }
    throw new Error('Failed to export checkpoint');
  } catch (error) {
    console.error('Failed to export checkpoint:', error);
    throw error;
  }
}

export async function activateProfile(profileName) {
  try {
    const response = await fetch(`/activate/${profileName}`, { method: 'POST' });
    if (response.ok) {
      return await response.json();
    }
    throw new Error(`Failed to activate profile ${profileName}`);
  } catch (error) {
    console.error(`Failed to activate profile ${profileName}:`, error);
    throw error;
  }
}

export async function getStorageList(path) {
  try {
    const response = await fetch(`/api/storage/list?path=${encodeURIComponent(path)}`);
    if (response.ok) {
      return await response.json();
    }
    return [];
  } catch (error) {
    console.error('Failed to list storage:', error);
    return [];
  }
}

export async function getStoragePreview(path, lines = 3) {
  try {
    const response = await fetch(
      `/api/storage/preview?path=${encodeURIComponent(path)}&n=${lines}`
    );
    if (response.ok) {
      return await response.json();
    }
    return null;
  } catch (error) {
    console.error('Failed to get preview:', error);
    return null;
  }
}
