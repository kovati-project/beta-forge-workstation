import { useEffect, useRef } from 'react';
import { useApp } from '../context/AppContext';

export function useGpuStatus() {
  const { state, setGpuStatus, setLastSwitched } = useApp();
  const intervalRef = useRef(null);

  useEffect(() => {
    const pollGpuStatus = async () => {
      try {
        const response = await fetch('/status');
        if (response.ok) {
          const data = await response.json();
          setGpuStatus(data);
        }
      } catch (error) {
        console.error('Failed to fetch GPU status:', error);
      }
    };

    // Initial poll
    pollGpuStatus();

    // Set up polling: 1s when switching, 3s otherwise
    const interval = state.switching ? 1000 : 3000;
    intervalRef.current = setInterval(pollGpuStatus, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [state.switching, setGpuStatus, setLastSwitched]);
}
