import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { captured, stubApi } from '../test/api';
import { HypothesisScreen } from './HypothesisScreen';

function renderWith(id: string, routes: Record<string, unknown>) {
  vi.stubGlobal('fetch', stubApi(routes).fetch);
  return render(<HypothesisScreen id={id} />);
}

describe('HypothesisScreen', () => {
  it('heads the page with the hypothesis, its status and the commit that froze it', async () => {
    renderWith('demo_momentum', { '/api/hypotheses/demo_momentum': captured.momentum });

    expect(await screen.findByRole('heading', { name: 'demo_momentum' })).toBeInTheDocument();
    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(screen.getByText(captured.momentum.hypothesis.frozenAtCommit.slice(0, 7))).toBeInTheDocument();
  });

  it('shows the API problem for an unknown hypothesis', async () => {
    renderWith('momentum_v1', {
      '/api/hypotheses/momentum_v1': new Response(
        JSON.stringify({ title: "Unknown hypothesis 'momentum_v1'", status: 404 }),
        { status: 404, headers: { 'Content-Type': 'application/problem+json' } },
      ),
    });

    expect(await screen.findByText("Unknown hypothesis 'momentum_v1'")).toBeInTheDocument();
  });
});
