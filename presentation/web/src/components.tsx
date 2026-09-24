import type { ReactNode } from 'react';
import type { ApiError } from './api';
import { QF } from './design-system';

export function PageHead(props: { eyebrow?: ReactNode; title: ReactNode; sub?: ReactNode; side?: ReactNode }) {
  return (
    <div className="qf-pagehead">
      <div className="qf-pagehead__titles">
        {props.eyebrow && <div className="qf-eyebrow">{props.eyebrow}</div>}
        <h1 className="qf-pagehead__title">{props.title}</h1>
        {props.sub && <div className="qf-pagehead__sub">{props.sub}</div>}
      </div>
      {props.side}
    </div>
  );
}

export function Loading() {
  return <p className="qf-muted">Loading…</p>;
}

export function ErrorNotice({ error }: { error: ApiError }) {
  return (
    <QF.Callout tone="danger" title={error.message}>
      {error.detail && <code className="qf-code">{error.detail}</code>}
    </QF.Callout>
  );
}

/** REQ-743: synthetic numbers are never shown without saying so. */
export function SyntheticNotice() {
  return (
    <QF.Callout tone="warning" title="Synthetic data, not a research result">
      These runs read generated prices (data source <code className="qf-code">synthetic</code>). They show
      what the pipeline produces; they say nothing about any market.
    </QF.Callout>
  );
}

export function Disclaimer() {
  return (
    <div className="qf-disclaimer">
      All figures are historical simulations, net of the stated cost model, computed by quantlab. They
      describe past behaviour; nothing here is a recommendation to trade.
    </div>
  );
}

export function Command({ children }: { children: string }) {
  return <code className="qf-code">{children}</code>;
}
