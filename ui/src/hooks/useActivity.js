import { useEffect, useRef, useState } from 'react';

export function useActivity() {
  const [activity, setActivity] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const pollActivity = async () => {
      try {
        const response = await fetch('/api/activity');
        if (response.ok) {
          const data = await response.json();
          setActivity(data);
          setError(null);
        } else {
          setError('API unreachable');
        }
      } catch (err) {
        setError('API unreachable');
      }
    };

    // Initial poll
    pollActivity();

    // Set up polling: 30s interval
    intervalRef.current = setInterval(pollActivity, 30000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return { activity, error };
}
