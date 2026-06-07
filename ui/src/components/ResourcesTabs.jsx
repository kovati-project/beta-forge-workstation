import { Link, useSearchParams } from 'react-router-dom';
import './ResourcesTabs.css';

const TABS = ['models', 'datasets', 'checkpoints', 'vectors', 'storage'];

export function ResourcesTabs({ activeTab, onChange }) {
  const [searchParams, setSearchParams] = useSearchParams();

  const handleTabClick = (tab) => {
    setSearchParams({ tab });
    onChange?.(tab);
  };

  return (
    <div className="resources-tabs">
      {TABS.map((tab) => (
        <button
          key={tab}
          className={`resources-tab ${activeTab === tab ? 'active' : ''}`}
          onClick={() => handleTabClick(tab)}
        >
          {tab.charAt(0).toUpperCase() + tab.slice(1)}
        </button>
      ))}
    </div>
  );
}
