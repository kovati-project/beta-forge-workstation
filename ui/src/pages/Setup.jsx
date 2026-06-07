import { useEffect, useState } from 'react';
import SetupWizard from '../components/setup/SetupWizard';
import { setupAPI } from '../utils/setupAPI';

export function Setup() {
  const [isComplete, setIsComplete] = useState(null);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const status = await setupAPI.getStatus();
        setIsComplete(status.complete);
        
        // If already complete, redirect to dashboard
        if (status.complete) {
          setTimeout(() => {
            window.location.href = '/#/dashboard';
          }, 1000);
        }
      } catch (err) {
        console.error('Failed to check setup status:', err);
      }
    };

    checkStatus();
  }, []);

  if (isComplete === null) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
        background: 'var(--bg)',
      }}>
        <div className="spinner"></div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
        background: 'var(--bg)',
        color: 'var(--text)',
      }}>
        <p>Setup already complete. Redirecting to dashboard...</p>
      </div>
    );
  }

  return <SetupWizard />;
}
