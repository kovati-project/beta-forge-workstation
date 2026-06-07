import { useEffect, useRef, useState } from 'react';

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
          setProfiles(data.profiles || []);
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
