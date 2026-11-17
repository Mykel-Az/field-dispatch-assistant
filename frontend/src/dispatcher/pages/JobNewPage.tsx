import { useNavigate } from 'react-router-dom';
import BackLink from '../../shared/components/BackLink';
import { useBack } from '../../shared/useBack';
import { ui } from '../../shared/ui';
import JobForm from '../components/JobForm';

export default function JobNewPage() {
  const navigate = useNavigate();
  const { go } = useBack();
  return (
    <section className="mx-auto max-w-3xl">
      <BackLink />
      <h1 className={`${ui.h1} mt-2`}>New job</h1>
      <div className={ui.card}>
        <JobForm
          onCancel={go}
          onSaved={(job) => navigate(`/jobs/${job.id}`, { replace: true })}
        />
      </div>
    </section>
  );
}
