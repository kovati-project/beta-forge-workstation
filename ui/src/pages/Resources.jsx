import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ResourcesTabs } from '../components/ResourcesTabs';
import { ModelsTab } from '../components/ModelsTab';
import { DatasetsTab } from '../components/DatasetsTab';
import { CheckpointsTab } from '../components/CheckpointsTab';
import { VectorsTab } from '../components/VectorsTab';
import { StorageTab } from '../components/StorageTab';
import './Resources.css';

export function Resources() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'models');

  useEffect(() => {
    setSearchParams({ tab: activeTab });
  }, [activeTab, setSearchParams]);

  const renderTabContent = () => {
    switch (activeTab) {
      case 'models':
        return <ModelsTab />;
      case 'datasets':
        return <DatasetsTab />;
      case 'checkpoints':
        return <CheckpointsTab />;
      case 'vectors':
        return <VectorsTab />;
      case 'storage':
        return <StorageTab />;
      default:
        return <ModelsTab />;
    }
  };

  return (
    <div className="resources-page">
      <div className="page-header">
        <h1>Resources</h1>
      </div>
      <ResourcesTabs activeTab={activeTab} onChange={setActiveTab} />
      <div className="tab-content">
        {renderTabContent()}
      </div>
    </div>
  );
}
