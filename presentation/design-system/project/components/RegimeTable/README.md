# RegimeTable

Performance conditional on volatility regime (terciles of realized vol), with a diverging Sharpe bar per row.

- Each row is `{regime: 'low'|'mid'|'high', label, share, sharpe, ret, maxdd, hit}`, with fractions for the percentages.
- Use it to show whether an average hides a regime where the strategy fails when it hurts most.
