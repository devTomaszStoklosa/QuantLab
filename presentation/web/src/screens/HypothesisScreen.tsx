import { api } from '../api';
import { Disclaimer, ErrorNotice, Loading, PageHead } from '../components';
import { QF } from '../design-system';
import { range, sha } from '../format';
import { useResource } from '../resource';
import { href } from '../route';

export function HypothesisScreen({ id }: { id: string }) {
  const detail = useResource(`hypothesis:${id}`, () => api.hypothesis(id));

  if (detail.state === 'loading') return <Loading />;
  if (detail.state === 'failed') return <ErrorNotice error={detail.error} />;

  const h = detail.data.hypothesis;
  return (
    <>
      <PageHead
        eyebrow={<a href={href.registry}>Hypothesis registry</a>}
        title={<span className="qf-num">{h.hypothesis}</span>}
        sub={
          <>
            <QF.StatusBadge status={h.status} />
            <span>{h.strategy}</span>
            <span className="qf-num">training {range(h.trainingStart, h.trainingEnd)}</span>
            <span>
              frozen at <code className="qf-code">{sha(h.frozenAtCommit)}</code>
            </span>
          </>
        }
      />
      <Disclaimer />
    </>
  );
}
