import { Link, useNavigate } from 'react-router-dom';
import { ui } from '../../shared/ui';
import JobForm from '../components/JobForm';

export default function JobNewPage() {
  const navigate = useNavigate();
  return (
    <section className="mx-auto max-w-3xl">
      <Link to="/jobs" className="text-sm text-brand hover:underline">← All jobs</Link>
      <h1 className={`${ui.h1} mt-2`}>New job</h1>
      <div className={ui.card}>
        <JobForm
          onCancel={() => navigate('/jobs')}
          onSaved={(job) => navigate(`/jobs/${job.id}`)}
        />
      </div>
    </section>
  );
}
