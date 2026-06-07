import { NVLinkTopology } from '../components/NVLinkTopology';
import { SwitchingBanner } from '../components/SwitchingBanner';
import { ProfileGrid } from '../components/ProfileGrid';
import { useLoadouts } from '../hooks/useLoadouts';
import './Loadout.css';

export function Loadout() {
  const { profiles, error } = useLoadouts();

  return (
    <div className="loadout-page">
      <NVLinkTopology />
      <SwitchingBanner />
      <ProfileGrid profiles={profiles} loading={!profiles} error={error} />
    </div>
  );
}
