import { useState, useEffect, useRef, useCallback } from 'react';
import { getInitialLogs } from '../utils/monitorAPI';
import './LogViewerSection.css';

export function LogViewerSection() {
  const [serviceName, setServiceName] = useState('axolotl');
  const [logLines, setLogLines] = useState([]);
  const [filteredLines, setFilteredLines] = useState([]);
  const [logLevel, setLogLevel] = useState('ALL');
  const [grepFilter, setGrepFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading, setLoading] = useState(true);

  const logContainerRef = useRef(null);
  const eventSourceRef = useRef(null);

  const services = [
    'axolotl',
    'vllm-pair-a',
    'vllm-pair-b',
    'ollama',
    'whisper-stt',
    'piper-tts',
  ];

  // Parse log level from line
  const getLogLevel = (line) => {
    if (line.toUpperCase().includes('ERROR') || line.includes('❌'))
      return 'ERROR';
    if (line.toUpperCase().includes('WARN') || line.includes('⚠')) return 'WARN';
    if (line.toUpperCase().includes('INFO') || line.includes('ℹ'))
      return 'INFO';
    return 'DEBUG';
  };

  // Filter lines based on log level and grep
  const applyFilters = useCallback(
    (lines) => {
      let filtered = lines;

      // Apply log level filter
      if (logLevel !== 'ALL') {
        filtered = filtered.filter((line) => getLogLevel(line) === logLevel);
      }

      // Apply grep filter
      if (grepFilter) {
        const regex = new RegExp(grepFilter, 'i');
        filtered = filtered.filter((line) => regex.test(line));
      }

      return filtered;
    },
    [logLevel, grepFilter]
  );

  // Load initial logs
  useEffect(() => {
    const loadLogs = async () => {
      setLoading(true);
      const data = await getInitialLogs(serviceName, 200);
      const lines = data.lines || [];
      setLogLines(lines);
      setFilteredLines(applyFilters(lines));
      setLoading(false);

      // Auto-scroll to bottom
      if (logContainerRef.current) {
        setTimeout(
          () =>
            (logContainerRef.current.scrollTop =
              logContainerRef.current.scrollHeight),
          0
        );
      }
    };

    loadLogs();

    // Close previous SSE if exists
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Open new SSE stream
    const eventSource = new EventSource(
      `/api/services/${serviceName}/logs/stream`
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const newLines = data.line ? [data.line] : [];

        setLogLines((prev) => {
          const updated = [...prev, ...newLines];
          // Keep only last 200 lines
          return updated.slice(-200);
        });

        // Apply filters to new lines
        setFilteredLines((prev) => {
          const allFiltered = applyFilters([
            ...logLines.slice(-199),
            ...newLines,
          ]);
          return allFiltered.slice(-200);
        });

        // Auto-scroll if enabled
        if (autoScroll && logContainerRef.current) {
          setTimeout(
            () =>
              (logContainerRef.current.scrollTop =
                logContainerRef.current.scrollHeight),
            0
          );
        }
      } catch (e) {
        console.error('Failed to parse log message:', e);
      }
    };

    eventSourceRef.current = eventSource;

    return () => {
      eventSource.close();
    };
  }, [serviceName]);

  // Update filters without reloading
  useEffect(() => {
    setFilteredLines(applyFilters(logLines));
  }, [logLevel, grepFilter, applyFilters]);

  const highlightGrep = (line) => {
    if (!grepFilter) return line;
    const regex = new RegExp(`(${grepFilter})`, 'gi');
    return line.replace(
      regex,
      '<mark class="grep-highlight">$1</mark>'
    );
  };

  return (
    <div className="log-viewer-section">
      <div className="log-controls">
        <select
          value={serviceName}
          onChange={(e) => setServiceName(e.target.value)}
          className="service-select"
        >
          {services.map((svc) => (
            <option key={svc} value={svc}>
              {svc}
            </option>
          ))}
        </select>

        <div className="filter-buttons">
          {['ALL', 'INFO', 'WARN', 'ERROR'].map((level) => (
            <button
              key={level}
              className={`level-btn ${logLevel === level ? 'active' : ''}`}
              onClick={() => setLogLevel(level)}
            >
              {level}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="grep filter..."
          value={grepFilter}
          onChange={(e) => setGrepFilter(e.target.value)}
          className="grep-input"
        />

        <label className="scroll-toggle">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
          />
          <span>Auto-scroll</span>
        </label>
      </div>

      {loading ? (
        <div className="log-content loading">Loading logs...</div>
      ) : (
        <div
          ref={logContainerRef}
          className="log-content"
          onScroll={() => {
            // Disable auto-scroll if user scrolls up
            if (logContainerRef.current) {
              const { scrollTop, scrollHeight, clientHeight } =
                logContainerRef.current;
              if (scrollTop < scrollHeight - clientHeight - 10) {
                setAutoScroll(false);
              } else {
                setAutoScroll(true);
              }
            }
          }}
        >
          {filteredLines.length === 0 ? (
            <div className="no-logs">No logs match filters</div>
          ) : (
            filteredLines.map((line, idx) => {
              const level = getLogLevel(line);
              const levelClass = `level-${level.toLowerCase()}`;
              return (
                <div key={idx} className={`log-line ${levelClass}`}>
                  <span
                    dangerouslySetInnerHTML={{
                      __html: highlightGrep(line),
                    }}
                  />
                </div>
              );
            })
          )}
        </div>
      )}

      <div className="log-footer">
        Showing {filteredLines.length} of {logLines.length} lines
      </div>
    </div>
  );
}
