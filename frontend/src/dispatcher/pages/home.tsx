import { useEffect, useState } from 'react';
import { checkHealth, fetchSkills } from '../../shared/api/client';

export default function DashboardPage() {
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    checkHealth()
      .then((data) => setStatus(data.status === 'ok' ? 'ok' : 'error'))
      .catch(() => setStatus('error'));
  }, []);

  const handleFetchSkills = async () => {
    setLoading(true);
    setMessage('Fetching skills...');
    try {
      const skills = await fetchSkills();
      setMessage(`Skills: ${skills.map((s) => s.name).join(', ')}`);
    } catch {
      setMessage('Failed to fetch skills');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Field Dispatch Assistant</h1>
      <p>
        API: <strong>{status === 'loading' ? 'checking...' : status}</strong>
      </p>
      <button onClick={handleFetchSkills} disabled={loading || status !== 'ok'}>
        {loading ? 'Fetching...' : 'Fetch Skills'}
      </button>
      {message && <p>{message}</p>}
    </div>
  );
}