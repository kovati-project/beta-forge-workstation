import { useEffect, useRef } from 'react';
import { useApp } from '../context/AppContext';

export function useServices() {
  const { setServices } = useApp();
  const intervalRef = useRef(null);

  useEffect(() => {
    const pollServices = async () => {
      try {
        const response = await fetch('/api/services');
        if (response.ok) {
          const data = await response.json();
          setServices({ services: data });
        }
      } catch (error) {
        console.error('Failed to fetch services:', error);
      }
    };

    // Initial poll
    pollServices();

    // Set up polling: 10s interval
    intervalRef.current = setInterval(pollServices, 10000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [setServices]);
}
