import React, { useEffect, useState } from 'react';
import { checkHealth, fetchSkills} from '../../shared/api/client';

export default function DashboardPage() {
  const [status, setStatus] = useState<string>('loading');
  const [actionMessage, setActionMessage] = useState<string>('');
  const [isrequestingSkills, setIsRequestingSkills] = useState<boolean>(false);

  useEffect(() => {
    checkHealth()
      .then((data) => {
        // Assuming your Django health endpoint returns { "status": "ok" }
        if (data.status === 'ok') {
          setStatus('ok');
        } else {
          setStatus('error');
        }
      })
      .catch(() => {
        setStatus('error');
      });
  }, []);


  const handleFetchSkills = async () => {
    setIsRequestingSkills(true);
    setActionMessage('Fetching skills...');
    try {
      const data = await fetchSkills();
        setActionMessage(`Fetched skills: ${data.skills.join(', ')}`);
    } catch (error) {
      setActionMessage('Failed to fetch skills');
    } finally {
      setIsRequestingSkills(false);
    }
};


  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Field Dispatch Assistant</h1>
      <p>
        API:{' '}
        <strong>
          {status === 'loading' && 'checking...'}
          {status === 'ok' && 'ok'}
          {status === 'error' && 'error'}
        </strong>
      </p>

        <button onClick={handleFetchSkills} disabled={isrequestingSkills}>
            {isrequestingSkills ? 'Fetching...' : 'Fetch Skills'}
        </button>
        <p>{actionMessage}</p>


        <div style={{ marginTop: '2rem', borderTop: '1px solid #ccc', paddingTop: '1rem' }}>
        <h3>Skills Control</h3>
        <button 
          onClick={handleFetchSkills} disabled={isrequestingSkills || status !== 'ok'}
          style={{
            padding: '0.5rem 1rem',
            cursor: isrequestingSkills || status !== 'ok' ? 'not-allowed' : 'pointer',
            backgroundColor: '#007bff',
            color: '#fff',
            border: 'none',
            borderRadius: '4px'
          }}
        >
          {isrequestingSkills ? 'Fetching...' : 'Fetch Skills'}
        </button>
        
        {actionMessage && (
          <p style={{ marginTop: '1rem', color: '#555', fontStyle: 'italic' }}>
            {actionMessage}
          </p>
        )}
      </div>

    </div>
  );
}