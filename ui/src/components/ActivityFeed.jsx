import { useActivity } from '../hooks/useActivity';
import { Tag } from './Tag';
import { Panel } from './Panel';
import './ActivityFeed.css';

function formatTimestamp(ts) {
  if (!ts) return '—';
  
  const date = new Date(ts * 1000);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);
  
  const mins = Math.floor(diff / 60);
  const hours = Math.floor(diff / 3600);
  const days = Math.floor(diff / 86400);
  
  // Same day, different time
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  
  // Yesterday
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return 'Yest';
  }
  
  // Older
  if (days > 0) return `${days}d`;
  
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function getTagVariant(eventType) {
  switch (eventType) {
    case 'SWITCH':
      return 'cyan';
    case 'BACKUP':
      return 'green';
    case 'TRAIN':
      return 'amber';
    case 'UPDATE':
      return 'green';
    case 'RESTART':
      return 'gray';
    case 'ERROR':
      return 'red';
    default:
      return 'gray';
  }
}

export function ActivityFeed() {
  const { activity, error } = useActivity();

  const events = activity?.events || [];

  return (
    <Panel title="ACTIVITY">
      <div className="activity-feed">
        {error && (
          <div className="activity-error">⚠ API unreachable — retrying…</div>
        )}
        {events.length === 0 ? (
          <div className="activity-empty">No recent activity</div>
        ) : (
          events.map((event, idx) => (
            <div key={idx} className="activity-item">
              <div className="activity-timestamp">
                {formatTimestamp(event.ts)}
              </div>
              <Tag variant={getTagVariant(event.type)}>
                {event.type}
              </Tag>
              <div className="activity-detail">
                {event.detail}
              </div>
            </div>
          ))
        )}
      </div>
    </Panel>
  );
}
