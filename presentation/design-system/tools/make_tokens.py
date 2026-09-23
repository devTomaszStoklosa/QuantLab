import json
import sys
from pathlib import Path

C = [
 # name, light, dark, usage
 ("ground", "#f4f3ef", "#0d0f11", "App background behind panels. Warm paper in light, near-black graphite in dark."),
 ("surface", "#ffffff", "#15181b", "Panels, tables, charts, dialogs: every raised working surface."),
 ("surface-sunken", "#ebe9e3", "#0a0b0d", "Wells inside a panel: code, table headers, sidebar, chart gutters."),
 ("surface-hover", "#f0eee8", "#1c2024", "Row and nav-item hover fill on surface."),
 ("line", "#dddad2", "#272b30", "Hairlines: panel borders, table rules, chart gridlines' frame. Decorative; never the only boundary of a control."),
 ("line-strong", "#8f8b81", "#646b73", "Control borders (inputs, checkboxes, secondary buttons). Meets 3:1 on surface and ground in both themes."),
 ("ink", "#16181b", "#ebe9e4", "Primary text and the strategy equity line, on ground, surface and surface-sunken."),
 ("ink-muted", "#565a61", "#9ea4ac", "Secondary text, metadata, axis labels, table headers, on ground, surface and surface-sunken (≥4.5:1 in both themes)."),
 ("ink-faint", "#8b8f96", "#646a72", "Disabled text and placeholder only. Fails 4.5:1 by design; never for information."),
 ("ink-inverse", "#f4f3ef", "#0d0f11", "Text on surface-inverse (tooltips, the toast)."),
 ("surface-inverse", "#16181b", "#ebe9e4", "Tooltip and toast fill."),
 ("forge", "#c2461a", "#f08447", "The brand ember. Primary action fill, logo spark, the one running job. Rare by design: one forge element per view."),
 ("on-forge", "#ffffff", "#1a0c04", "Text and icons on a forge fill."),
 ("forge-soft", "#fbe6da", "#3a1f12", "Tint behind forge text: the selected nav item, a primary-hover wash."),
 ("forge-ink", "#a63b14", "#f59a6b", "Forge as text: links and the selected nav label, on ground, surface and forge-soft."),
 ("focus", "#2256a3", "#8fb6ff", "Keyboard focus ring: 2px solid, 2px offset. ≥3:1 on every surface in both themes."),
 ("partition-is", "#61666f", "#8a9099", "In-sample data: the window parameters were fitted on. Neutral on purpose; in-sample numbers are the least trustworthy."),
 ("partition-is-soft", "#eceef1", "#1d2126", "In-sample band fill behind charts and the IS training bar in walk-forward lanes."),
 ("partition-oos", "#2f64b1", "#79a3e6", "Out-of-sample (walk-forward test) data: bands, fold bars, OOS tags. As text on surface and ground."),
 ("partition-oos-soft", "#e3ebf7", "#15233a", "Out-of-sample band fill behind charts; testing badge fill."),
 ("partition-holdout", "#5b47b8", "#aa9bf2", "The frozen holdout: hatch strokes, seal border, lock glyphs, holdout tags. As text on surface and holdout-soft."),
 ("partition-holdout-soft", "#ece8fa", "#211b3b", "Holdout band and seal fill. Always paired with the hatch pattern, never colour alone."),
 ("status-proposed", "{ink-muted}", None, "Proposed hypothesis: registered, no data touched yet."),
 ("status-testing", "{partition-oos}", None, "Testing: runs in progress on in-sample or walk-forward data."),
 ("status-confirmed", "#17745f", "#4cc3a2", "Confirmed: survived walk-forward AND the one-look holdout. Text on surface and confirmed-soft."),
 ("status-confirmed-soft", "#ddf1ea", "#0f2a23", "Confirmed badge and verdict-banner fill."),
 ("status-rejected", "#3b434e", "#c0c7d1", "Rejected: a finished, documented result. Graphite, not red: rejection is knowledge, not an error."),
 ("status-rejected-soft", "#e5e7ea", "#252a31", "Rejected badge and verdict-banner fill."),
 ("status-inconclusive", "#8a5d00", "#e3b24f", "Inconclusive: evidence too weak either way. Text on surface and inconclusive-soft."),
 ("status-inconclusive-soft", "#f6ecd2", "#2e2410", "Inconclusive badge and verdict-banner fill."),
 ("danger", "#b3261e", "#ff8a80", "Integrity alarms only: look-ahead leak, holdout breach, failed gate, destructive action. As text on surface and danger-soft."),
 ("danger-soft", "#fbe3e1", "#3a1614", "Danger callout fill."),
 ("warning", "#8a5d00", "#e3b24f", "Methodology warnings that do not block (few trades, short window). As text on surface and warning-soft."),
 ("warning-soft", "#f6ecd2", "#2e2410", "Warning callout fill."),
 ("gain", "#2256a3", "#79a8f0", "Positive P&L and returns: heatmap cells, positive bars. Blue, never green, so gain/loss survives red–green colour blindness."),
 ("loss", "#b8322a", "#ff8a7a", "Negative P&L and returns, drawdown line, cost deductions."),
 ("drawdown", "rgba(184, 50, 42, 0.16)", "rgba(255, 138, 122, 0.20)", "Area fill under the drawdown curve."),
 ("chart-benchmark", "#9a9ea5", "#6a7078", "Benchmark / buy-and-hold line: dashed, 1px, behind the strategy line."),
 ("chart-grid", "#ebe9e3", "#20242a", "Chart gridlines. Horizontal only, 1px."),
 ("regime-low", "#d3d9e0", "#2a3440", "Low-volatility regime (bottom tercile of realized vol). Swatches and regime strips."),
 ("regime-mid", "#8e9bad", "#566579", "Mid-volatility regime (middle tercile)."),
 ("regime-high", "#3d4a5c", "#a6b5c9", "High-volatility regime (top tercile). Darkest in light, lightest in dark: stress always has the most contrast."),
 ("scrim", "rgba(13, 15, 17, 0.48)", "rgba(0, 0, 0, 0.64)", "Overlay behind dialogs (the holdout-unseal ceremony)."),
]

colors = []
for n, l, d, u in C:
    v = {"light": l} if d is None else {"light": l, "dark": d}
    colors.append({"name": n, "value": v, "usage": u})

tokens = {
 "name": "QuantForge",
 "version": 1,
 "color": {
  "themes": [{"id": "light", "name": "Paper"}, {"id": "dark", "name": "Graphite"}],
  "tokens": colors,
 },
 "type": {
  "fonts": [],
  "families": {
   "sans": "\"IBM Plex Sans\", \"Helvetica Neue\", Arial, sans-serif",
   "mono": "\"IBM Plex Mono\", ui-monospace, \"SF Mono\", Menlo, Consolas, monospace",
   "serif": "\"Source Serif 4\", \"Source Serif Pro\", Georgia, serif",
  },
  "groups": [
   {"name": "Interface", "family": "sans", "styles": [
     {"name": "text-display", "fontSize": "36px", "lineHeight": "40px", "fontWeight": 600, "letterSpacing": "-0.02em", "sample": "Hypotheses, not charts.", "usage": "Page titles on the registry and tear sheet. One per screen."},
     {"name": "text-h1", "fontSize": "24px", "lineHeight": "30px", "fontWeight": 600, "letterSpacing": "-0.01em", "sample": "H-001 · Time-series momentum", "usage": "Hypothesis title in the workspace header."},
     {"name": "text-h2", "fontSize": "16px", "lineHeight": "22px", "fontWeight": 600, "sample": "Walk-forward validation", "usage": "Panel titles."},
     {"name": "text-body", "fontSize": "14px", "lineHeight": "21px", "fontWeight": 400, "sample": "Parameters were fitted on 2019–2022 and never revisited.", "usage": "Default UI and prose text."},
     {"name": "text-small", "fontSize": "12.5px", "lineHeight": "18px", "fontWeight": 400, "sample": "Updated 2 hours ago by T. Stokłosa", "usage": "Metadata, table cells in dense tables, captions."},
     {"name": "text-eyebrow", "fontSize": "11px", "lineHeight": "14px", "fontWeight": 600, "letterSpacing": "0.08em", "sample": "PRE-REGISTERED CRITERIA", "usage": "Uppercase section labels above a block. Uppercase via CSS, written in sentence case."},
   ]},
   {"name": "Research", "family": "serif", "styles": [
     {"name": "text-statement", "fontSize": "19px", "lineHeight": "28px", "fontWeight": 400, "sample": "Assets with positive 12-week returns keep outperforming over the next week, net of realistic costs.", "usage": "The hypothesis statement and research-log conclusions: the scientific claim, set apart from the UI chrome."},
     {"name": "text-note", "fontSize": "15px", "lineHeight": "23px", "fontWeight": 400, "fontStyle": "italic", "sample": "Momentum premium attributed to investor under-reaction (Moskowitz, Ooi, Pedersen 2012).", "usage": "Economic rationale and analyst annotations."},
   ]},
   {"name": "Numbers", "family": "mono", "styles": [
     {"name": "text-metric-xl", "fontSize": "30px", "lineHeight": "34px", "fontWeight": 500, "letterSpacing": "-0.02em", "sample": "0.64", "usage": "The headline metric in a Metric tile (Sharpe, CAGR). Tabular figures."},
     {"name": "text-metric", "fontSize": "13px", "lineHeight": "20px", "fontWeight": 500, "sample": "−18.4%  1.12  [0.31, 0.97]", "usage": "Every number in tables, legends and rails. Tabular figures, U+2212 minus."},
     {"name": "text-code", "fontSize": "12px", "lineHeight": "18px", "fontWeight": 400, "sample": "3f9a2c1 · lookback=12w", "usage": "Commit SHAs, parameters, config keys."},
   ]},
  ],
 },
 "spacing": {"tokens": [
   {"name": "space-1", "value": "4px", "usage": "Icon-to-label gap, badge padding."},
   {"name": "space-2", "value": "8px", "usage": "Gap inside controls and between related metadata."},
   {"name": "space-3", "value": "12px", "usage": "Table cell padding, gap between metric tiles."},
   {"name": "space-4", "value": "16px", "usage": "Panel padding, page gutter on narrow screens."},
   {"name": "space-5", "value": "24px", "usage": "Gap between panels; page gutter."},
   {"name": "space-6", "value": "32px", "usage": "Gap between page sections."},
   {"name": "space-7", "value": "48px", "usage": "Top of page to title on registry and tear sheet."},
 ]},
 "radius": {"tokens": [
   {"name": "radius-xs", "value": "2px", "usage": "Chart bars, heatmap cells, partition tags."},
   {"name": "radius-sm", "value": "4px", "usage": "Buttons, inputs, badges."},
   {"name": "radius-md", "value": "6px", "usage": "Panels, dialogs, the holdout seal."},
   {"name": "radius-pill", "value": "999px", "usage": "Stage-rail nodes and toggles only."},
 ]},
 "shadow": {"tokens": [
   {"name": "shadow-panel", "value": {"light": "0 1px 0 rgba(22, 24, 27, 0.04)", "dark": "none"}, "usage": "Panels. Borders do the work; the shadow is a whisper."},
   {"name": "shadow-pop", "value": {"light": "0 8px 24px rgba(22, 24, 27, 0.14), 0 1px 2px rgba(22, 24, 27, 0.08)", "dark": "0 8px 24px rgba(0, 0, 0, 0.5), 0 0 0 1px #272b30"}, "usage": "Menus, tooltips and dialogs: anything floating above the page."},
 ]},
}

# ---- contrast checks
def hexrgb(h):
    h = h.lstrip('#'); return [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
def lum(h):
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in hexrgb(h)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def cr(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True); return (la + 0.05) / (lb + 0.05)
val = {}
for n, l, d, u in C:
    val[n] = {"light": l, "dark": d if d else l}
def res(n, t):
    x = val[n][t]
    if x.startswith('{'): return res(x[1:-1], t)
    return x
pairs = [
 ("ink", ["ground", "surface", "surface-sunken", "surface-hover"], 4.5),
 ("ink-muted", ["ground", "surface", "surface-sunken", "surface-hover"], 4.5),
 ("ink-inverse", ["surface-inverse"], 4.5),
 ("on-forge", ["forge"], 4.5),
 ("forge-ink", ["ground", "surface", "forge-soft"], 4.5),
 ("focus", ["ground", "surface", "surface-sunken"], 3),
 ("line-strong", ["ground", "surface"], 3),
 ("partition-oos", ["surface", "ground", "partition-oos-soft"], 4.5),
 ("partition-holdout", ["surface", "partition-holdout-soft"], 4.5),
 ("partition-is", ["surface", "partition-is-soft"], 4.5),
 ("status-confirmed", ["surface", "status-confirmed-soft"], 4.5),
 ("status-rejected", ["surface", "status-rejected-soft"], 4.5),
 ("status-inconclusive", ["surface", "status-inconclusive-soft"], 4.5),
 ("danger", ["surface", "danger-soft"], 4.5),
 ("warning", ["surface", "warning-soft"], 4.5),
 ("gain", ["surface"], 4.5),
 ("loss", ["surface"], 4.5),
 ("regime-high", ["surface"], 3),
 ("chart-benchmark", ["surface"], 2.2),
]
bad = 0
for fg, bgs, need in pairs:
    for t in ("light", "dark"):
        for bg in bgs:
            r = cr(res(fg, t), res(bg, t))
            flag = "" if r >= need else "   <-- FAIL"
            if flag: bad += 1
            print(f"{t:5} {fg:20} on {bg:24} {r:5.2f} (need {need}){flag}")
Path(sys.argv[1]).write_text(json.dumps(tokens, indent=1, ensure_ascii=False))
print("fails:", bad)
