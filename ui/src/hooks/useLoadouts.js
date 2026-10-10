import { useEffect, useRef, useState } from 'react';

// GET /loadouts returns a dict keyed by profile name (no `profiles` wrapper).
// ProfileGrid/ProfileCard expect an array with `name` on each entry, and read
// GPU indices as numbers from `gpus` (the API sends `exclusive_gpus` as strings).
export function normalizeLoadouts(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return [];
  }
  return Object.entries(data).map(([name, p]) => ({
    ...p,
    name,
    gpus: (p?.exclusive_gpus || []).map(Number),
  }));
}

export function useLoadouts() {
  const [profiles, setProfiles] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const pollLoadouts = async () => {
      try {
        const response = await fetch('/loadouts');
        if (response.ok) {
          const data = await response.json();
          setProfiles(normalizeLoadouts(data));
          setError(null);
        } else {
          setError('Failed to load profiles');
        }
      } catch (err) {
        setError('Failed to load profiles');
      }
    };

    // Initial poll
    pollLoadouts();

    // Poll on every status refresh (same as GPU polling)
    intervalRef.current = setInterval(pollLoadouts, 3000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return { profiles, error };
}
