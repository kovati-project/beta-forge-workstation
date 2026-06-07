// Settings API utilities

export async function getSecrets() {
  try {
    const response = await fetch('/api/secrets');
    if (response.ok) return await response.json();
    return { secrets: [] };
  } catch (error) {
    console.error('Failed to fetch secrets:', error);
    return { secrets: [] };
  }
}

export async function rotateSecret(key) {
  try {
    const response = await fetch(`/api/secrets/${key}/rotate`, {
      method: 'POST',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to rotate secret');
  } catch (error) {
    console.error('Failed to rotate secret:', error);
    throw error;
  }
}

export async function rotateAllSecrets() {
  try {
    const response = await fetch('/api/secrets/rotate-all', {
      method: 'POST',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to rotate all secrets');
  } catch (error) {
    console.error('Failed to rotate all secrets:', error);
    throw error;
  }
}

export async function getNetwork() {
  try {
    const response = await fetch('/api/network');
    if (response.ok) return await response.json();
    return {};
  } catch (error) {
    console.error('Failed to fetch network config:', error);
    return {};
  }
}

export async function updateJumpboxIP(jumpboxIP) {
  try {
    const response = await fetch('/api/network', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jumpbox_ip: jumpboxIP }),
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to update jumpbox IP');
  } catch (error) {
    console.error('Failed to update jumpbox IP:', error);
    throw error;
  }
}

export async function getAuthStatus() {
  try {
    const response = await fetch('/api/auth/status');
    if (response.ok) return await response.json();
    return { running: false };
  } catch (error) {
    console.error('Failed to fetch auth status:', error);
    return { running: false };
  }
}

export async function getAuthUsers() {
  try {
    const response = await fetch('/api/auth/users');
    if (response.ok) return await response.json();
    return { users: [] };
  } catch (error) {
    console.error('Failed to fetch auth users:', error);
    return { users: [] };
  }
}

export async function promoteUser(userId) {
  try {
    const response = await fetch(`/api/auth/users/${userId}/promote`, {
      method: 'POST',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to promote user');
  } catch (error) {
    console.error('Failed to promote user:', error);
    throw error;
  }
}

export async function demoteUser(userId) {
  try {
    const response = await fetch(`/api/auth/users/${userId}/demote`, {
      method: 'POST',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to demote user');
  } catch (error) {
    console.error('Failed to demote user:', error);
    throw error;
  }
}

export async function deleteUser(userId) {
  try {
    const response = await fetch(`/api/auth/users/${userId}`, {
      method: 'DELETE',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to delete user');
  } catch (error) {
    console.error('Failed to delete user:', error);
    throw error;
  }
}

export async function getStackImages() {
  try {
    const response = await fetch('/api/stack/images');
    if (response.ok) return await response.json();
    return { images: [] };
  } catch (error) {
    console.error('Failed to fetch stack images:', error);
    return { images: [] };
  }
}

export async function updateAllServices() {
  try {
    const response = await fetch('/api/stack/update', {
      method: 'POST',
    });
    if (response.ok) return response; // Return response for streaming
    throw new Error('Failed to update services');
  } catch (error) {
    console.error('Failed to update services:', error);
    throw error;
  }
}

export async function rollbackService(serviceName) {
  try {
    const response = await fetch(`/api/stack/rollback/${serviceName}`, {
      method: 'POST',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to rollback service');
  } catch (error) {
    console.error('Failed to rollback service:', error);
    throw error;
  }
}

export async function getBackupConfig() {
  try {
    const response = await fetch('/api/backup/config');
    if (response.ok) return await response.json();
    return { schedule: '0 6 * * *', destination: '/data/backups/' };
  } catch (error) {
    console.error('Failed to fetch backup config:', error);
    return { schedule: '0 6 * * *', destination: '/data/backups/' };
  }
}

export async function updateBackupSchedule(schedule) {
  try {
    const response = await fetch('/api/backup/config', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schedule }),
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to update backup schedule');
  } catch (error) {
    console.error('Failed to update backup schedule:', error);
    throw error;
  }
}

export async function getBackupHistory() {
  try {
    const response = await fetch('/api/backup/history');
    if (response.ok) return await response.json();
    return { backups: [] };
  } catch (error) {
    console.error('Failed to fetch backup history:', error);
    return { backups: [] };
  }
}

export async function runBackupNow() {
  try {
    const response = await fetch('/api/backup/run', {
      method: 'POST',
    });
    if (response.ok) return response; // Return response for streaming
    throw new Error('Failed to start backup');
  } catch (error) {
    console.error('Failed to start backup:', error);
    throw error;
  }
}

export async function deleteBackup(backupId) {
  try {
    const response = await fetch(`/api/backup/${backupId}`, {
      method: 'DELETE',
    });
    if (response.ok) return await response.json();
    throw new Error('Failed to delete backup');
  } catch (error) {
    console.error('Failed to delete backup:', error);
    throw error;
  }
}

export async function getPlatformSetup() {
  try {
    const response = await fetch('/api/platform/setup');
    if (response.ok) return await response.json();
    return { completed: false };
  } catch (error) {
    console.error('Failed to fetch platform setup:', error);
    return { completed: false };
  }
}
