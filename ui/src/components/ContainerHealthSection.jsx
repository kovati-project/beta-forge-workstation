import { useEffect, useState } from 'react';
import { getContainerMetrics } from '../utils/monitorAPI';
import './ContainerHealthSection.css';

export function ContainerHealthSection() {
  const [containers, setContainers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMetrics = async () => {
      const data = await getContainerMetrics();
      setContainers(data);
      setLoading(false);
    };
    loadMetrics();
  }, []);

  if (loading) {
    return <div className="loading">Loading container metrics...</div>;
  }

  return (
    <div className="container-health-section">
      <table className="containers-table">
        <thead>
          <tr>
            <th>Service</th>
            <th>Restarts</th>
            <th>Memory</th>
            <th>CPU</th>
            <th>OOM</th>
          </tr>
        </thead>
        <tbody>
          {containers.length === 0 ? (
            <tr>
              <td colSpan="5" className="empty">
                No containers
              </td>
            </tr>
          ) : (
            containers.map((container) => {
              const rowClass =
                container.restarts >= 3
                  ? 'alert'
                  : container.oom_killed
                    ? 'alert'
                    : '';
              const oomClass = container.oom_killed ? 'oom-alert' : '';

              return (
                <tr key={container.name} className={rowClass}>
                  <td className="service-name">{container.name}</td>
                  <td>{container.restarts}</td>
                  <td>{container.memory_mb} MB</td>
                  <td>{container.cpu_percent}%</td>
                  <td className={oomClass}>
                    {container.oom_killed ? (
                      <>
                        yes ⚠
                      </>
                    ) : (
                      'no'
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
