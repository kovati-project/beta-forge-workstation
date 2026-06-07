import { useEffect, useRef } from 'react';
import { useApp } from '../context/AppContext';

export function useAlerts() {
  const { setAlertCount } = useApp();
  const intervalRef = useRef(null);

  useEffect(() => {
    const pollAlerts = async () => {
      try {
        const response = await fetch('/api/alerts');
        if (response.ok) {
          const data = await response.json();
          const count = Array.isArray(data) ? data.length : 0;
          setAlertCount(count);
        }
      } catch (error) {
        console.error('Failed to fetch alerts:', error);
      }
    };

    // Initial poll
    pollAlerts();

    // Set up polling: 30s interval
    intervalRef.current = setInterval(pollAlerts, 30000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [setAlertCount]);
}
