import React, { useEffect, useRef, useState } from 'react';

export function useSystemMetrics() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const pollMetrics = async () => {
      try {
        const response = await fetch('/api/metrics/system');
        if (response.ok) {
          const data = await response.json();
          setMetrics(data);
          setError(null);
        } else {
          setError('API unreachable');
        }
      } catch (err) {
        setError('API unreachable');
      }
    };

    // Initial poll
    pollMetrics();

    // Set up polling: 10s interval
    intervalRef.current = setInterval(pollMetrics, 10000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return { metrics, error };
}
