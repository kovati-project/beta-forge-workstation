import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Shell } from './components/Shell';
import { Dashboard } from './pages/Dashboard';
import { Loadout } from './pages/Loadout';
import { Tools } from './pages/Tools';
import { Training } from './pages/Training';
import { Resources } from './pages/Resources';
import { Expose } from './pages/Expose';
import { Monitor } from './pages/Monitor';
import { Settings } from './pages/Settings';
import { Voice } from './pages/Voice';
import { Admin } from './pages/Admin';
import { Operations } from './pages/Operations';
import { Setup } from './pages/Setup';

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/setup" element={<Setup />} />
        <Route
          path="/*"
          element={
            <Shell>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/loadout" element={<Loadout />} />
                <Route path="/tools" element={<Tools />} />
                <Route path="/training" element={<Training />} />
                <Route path="/resources" element={<Resources />} />
                <Route path="/expose" element={<Expose />} />
                <Route path="/monitor" element={<Monitor />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/voice" element={<Voice />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="/operations" element={<Operations />} />
              </Routes>
            </Shell>
          }
        />
      </Routes>
    </HashRouter>
  );
}
