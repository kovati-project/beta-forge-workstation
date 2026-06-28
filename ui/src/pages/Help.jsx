import { useState } from 'react';
import './Help.css';
import { HelpNav } from '../components/help/HelpNav';
import { HelpCommonTasks } from '../components/help/sections/HelpCommonTasks';
import { HelpDashboard } from '../components/help/sections/HelpDashboard';
import { HelpLoadout } from '../components/help/sections/HelpLoadout';
import { HelpTools } from '../components/help/sections/HelpTools';
import { HelpTraining } from '../components/help/sections/HelpTraining';
import { HelpResources } from '../components/help/sections/HelpResources';
import { HelpExpose } from '../components/help/sections/HelpExpose';
import { HelpVoice } from '../components/help/sections/HelpVoice';
import { HelpMonitor } from '../components/help/sections/HelpMonitor';
import { HelpOperations } from '../components/help/sections/HelpOperations';
import { HelpAdmin } from '../components/help/sections/HelpAdmin';
import { HelpSettings } from '../components/help/sections/HelpSettings';

const sectionMap = {
  'common-tasks': (onNavigate) => <HelpCommonTasks onNavigate={onNavigate} />,
  'dashboard': () => <HelpDashboard />,
  'loadout': () => <HelpLoadout />,
  'tools': () => <HelpTools />,
  'training': () => <HelpTraining />,
  'resources': () => <HelpResources />,
  'expose': () => <HelpExpose />,
  'voice': () => <HelpVoice />,
  'monitor': () => <HelpMonitor />,
  'operations': () => <HelpOperations />,
  'admin': () => <HelpAdmin />,
  'settings': () => <HelpSettings />,
};

export function Help() {
  const [active, setActive] = useState('common-tasks');

  const renderSection = sectionMap[active];

  return (
    <div className="help-page">
      <HelpNav active={active} onChange={setActive} />
      <div className="help-content">
        {renderSection ? renderSection(setActive) : null}
      </div>
    </div>
  );
}
