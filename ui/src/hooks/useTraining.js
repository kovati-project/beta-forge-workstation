import { useEffect, useRef, useState } from 'react';

export function useTrainingStatus() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const response = await fetch('/api/training/status');
        if (response.ok) {
          const data = await response.json();
          setStatus(data);
          setError(null);
        }
      } catch (err) {
        setError(err.message);
      }
    };

    // Initial poll
    poll();

    // Poll every 5s
    intervalRef.current = setInterval(poll, 5000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return { status, error };
}

export function useLogStream(serviceName) {
  const [lines, setLines] = useState([]);
  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    if (!serviceName) return;

    const connectStream = () => {
      try {
        const es = new EventSource(`/api/services/${serviceName}/logs/stream`);

        es.onmessage = (event) => {
          const line = event.data;
          setLines((prev) => [...prev.slice(-199), line]);
          
          // Auto-scroll unless user scrolled up
          if (autoScrollRef.current) {
            setTimeout(() => {
              const logElement = document.querySelector('.live-training-logs');
              if (logElement) {
                logElement.scrollTop = logElement.scrollHeight;
              }
            }, 0);
          }
        };

        es.onerror = () => {
          es.close();
          setError('Log stream disconnected');
        };

        eventSourceRef.current = es;
      } catch (err) {
        setError(err.message);
      }
    };

    connectStream();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [serviceName]);

  return { lines, error, autoScrollRef };
}
