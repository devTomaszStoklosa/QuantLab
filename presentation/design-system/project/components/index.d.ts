import type * as React from 'react';

export type Partition = 'is' | 'oos' | 'holdout';
export type HypothesisStatus = 'proposed' | 'testing' | 'confirmed' | 'rejected' | 'inconclusive';
export type VerdictKind = 'confirmed' | 'rejected' | 'inconclusive';
export type StageState = 'passed' | 'failed' | 'active' | 'pending' | 'locked' | 'skipped';
export type IconName = 'check' | 'x' | 'lock' | 'unlock' | 'dash' | 'alert' | 'info' | 'flask' | 'commit' | 'clock' | 'arrow' | 'chevron' | 'search' | 'plus' | 'registry' | 'data' | 'signal' | 'run' | 'costs' | 'validate' | 'regime' | 'attribution' | 'book' | 'report' | 'shuffle' | 'repeat' | 'filter' | 'settings' | 'eye' | 'download' | 'pending';

export interface LogoProps { size?: number; wordmark?: boolean; className?: string }
export declare function Logo(props: LogoProps): React.ReactElement;

export interface IconProps { name: IconName; size?: number; strokeWidth?: number; label?: string; className?: string; style?: React.CSSProperties }
export declare function Icon(props: IconProps): React.ReactElement;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'seal'; size?: 'sm' | 'md'; icon?: IconName; iconRight?: IconName }
export declare function Button(props: ButtonProps): React.ReactElement;

export interface StatusBadgeProps { status: HypothesisStatus; size?: 'md' | 'lg'; children?: React.ReactNode }
export declare function StatusBadge(props: StatusBadgeProps): React.ReactElement;

export interface PartitionTagProps { partition: Partition; short?: boolean; sealed?: boolean; children?: React.ReactNode }
export declare function PartitionTag(props: PartitionTagProps): React.ReactElement;

export interface PanelProps { title?: React.ReactNode; subtitle?: React.ReactNode; icon?: IconName; tag?: React.ReactNode; actions?: React.ReactNode; footer?: React.ReactNode; flush?: boolean; children?: React.ReactNode; className?: string; style?: React.CSSProperties }
export declare function Panel(props: PanelProps): React.ReactElement;

/** Values arrive pre-computed and pre-formatted from quantlab; the UI never derives a metric. */
export interface MetricProps { label: React.ReactNode; value: React.ReactNode; unit?: string; partition?: Partition; sealed?: boolean; ci?: [string, string]; delta?: React.ReactNode; deltaTone?: 'gain' | 'loss' | 'neutral'; deltaLabel?: string; hint?: React.ReactNode; size?: 'md' | 'lg'; struck?: boolean }
export declare function Metric(props: MetricProps): React.ReactElement;
export interface MetricStripProps { items: MetricProps[]; columns?: number; children?: React.ReactNode }
export declare function MetricStrip(props: MetricStripProps): React.ReactElement;

export interface Stage { key: string; label: string; state: StageState; meta?: string }
export interface StageRailProps { stages: Stage[]; current?: string }
export declare function StageRail(props: StageRailProps): React.ReactElement;
export declare namespace StageRail { const STAGES: Array<[string, string]> }
export interface StageMeterProps { states: StageState[]; showCount?: boolean }
export declare function StageMeter(props: StageMeterProps): React.ReactElement;

export interface Criterion { label: string; threshold: string; result?: string; pass?: boolean; locked?: boolean }
export interface HypothesisCardProps { id: string; title?: string; status: HypothesisStatus; statement: string; rationale?: string; criteria?: Criterion[]; frozen?: { sha: string; date?: string }; owner?: string; updated?: string }
export declare function HypothesisCard(props: HypothesisCardProps): React.ReactElement;

export interface HoldoutSealProps { state?: 'sealed' | 'unsealed'; range: React.ReactNode; sha?: string; frozenAt?: string; criterion?: React.ReactNode; openedAt?: string; looksAllowed?: number; looksUsed?: number; children?: React.ReactNode }
export declare function HoldoutSeal(props: HoldoutSealProps): React.ReactElement;

export interface VerdictProps { verdict: VerdictKind; children: React.ReactNode; meta?: React.ReactNode; side?: React.ReactNode }
export declare function Verdict(props: VerdictProps): React.ReactElement;

export interface CalloutProps { tone?: 'info' | 'warning' | 'danger' | 'frozen'; title: React.ReactNode; icon?: IconName; children?: React.ReactNode }
export declare function Callout(props: CalloutProps): React.ReactElement;

export interface Check { state: 'pass' | 'warn' | 'fail' | 'na'; label: React.ReactNode; detail?: React.ReactNode; value?: React.ReactNode }
export declare function ChecksList(props: { items: Check[] }): React.ReactElement;

export interface TabItem { value: string; label: React.ReactNode; count?: number; icon?: IconName }
export interface TabsProps { items: TabItem[]; value?: string; defaultValue?: string; onChange?: (value: string) => void }
export declare function Tabs(props: TabsProps): React.ReactElement;

export interface FieldProps { label: React.ReactNode; hint?: React.ReactNode; error?: React.ReactNode; frozen?: boolean; children: React.ReactNode }
export declare function Field(props: FieldProps): React.ReactElement;
export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> { mono?: boolean }
export declare function TextInput(props: TextInputProps): React.ReactElement;
export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> { options: Array<string | { value: string; label: string }> }
export declare function Select(props: SelectProps): React.ReactElement;
export interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> { label: React.ReactNode }
export declare function Checkbox(props: CheckboxProps): React.ReactElement;

export interface Column<R = any> { key: string; label: React.ReactNode; numeric?: boolean; width?: number | string; format?: (v: any, row: R) => React.ReactNode; render?: (v: any, row: R) => React.ReactNode; tone?: (v: any, row: R) => 'gain' | 'loss' | 'dim' | null }
export interface DataTableProps<R = any> { columns: Column<R>[]; rows: R[]; dense?: boolean; selected?: string | number }
export declare function DataTable<R>(props: DataTableProps<R>): React.ReactElement;

export interface PartitionBand { kind: Partition; from: number; to: number; sealed?: boolean; label?: string; note?: string }
export interface EquityChartProps { series: number[]; drawdown?: number[]; benchmark?: number[]; partitions?: PartitionBand[]; xTicks?: Array<{ i: number; label: string }>; width?: number; height?: number; showDrawdown?: boolean; legend?: boolean; yFormat?: (v: number) => string; seriesLabel?: string; benchmarkLabel?: string; ariaLabel?: string }
export declare function EquityChart(props: EquityChartProps): React.ReactElement;
export interface SparklineProps { series: number[]; oosFrom?: number; holdoutFrom?: number; sealed?: boolean; width?: number; height?: number }
export declare function Sparkline(props: SparklineProps): React.ReactElement;
export interface CostWaterfallProps { steps: Array<{ label: string; value?: number; kind?: 'total' }>; unit?: string; width?: number }
export declare function CostWaterfall(props: CostWaterfallProps): React.ReactElement;
export interface WalkForwardProps { folds: Array<{ train: [number, number]; test: [number, number]; sharpe: number }>; span: [number, number]; holdout?: [number, number]; ticks?: Array<{ t: number; label: string }>; width?: number }
export declare function WalkForward(props: WalkForwardProps): React.ReactElement;
export interface PermutationTestProps { nullDist: number[]; observed: number; pValue?: number; bins?: number; width?: number; height?: number }
export declare function PermutationTest(props: PermutationTestProps): React.ReactElement;
export interface RegimeRow { regime: 'low' | 'mid' | 'high'; label?: string; share: number; sharpe: number; ret: number; maxdd: number; hit: number }
export declare function RegimeTable(props: { rows: RegimeRow[] }): React.ReactElement;
export interface MonthlyHeatmapProps { years: Array<{ year: number | string; months: Array<number | null>; total?: number | null; holdoutFrom?: number }>; scale?: number }
export declare function MonthlyHeatmap(props: MonthlyHeatmapProps): React.ReactElement;

export interface LogEntryProps { date: string; id: string; title: string; verdict: VerdictKind; conclusion: React.ReactNode; facts?: Array<[string, string]> }
export declare function LogEntry(props: LogEntryProps): React.ReactElement;

export interface DialogProps { title: React.ReactNode; subtitle?: React.ReactNode; icon?: IconName; tone?: 'default' | 'holdout'; footer?: React.ReactNode; scrim?: boolean; children?: React.ReactNode }
export declare function Dialog(props: DialogProps): React.ReactElement;

export interface NavItem { key?: string; label?: string; icon?: IconName; group?: string; href?: string }
export interface AppShellProps { active?: string; crumbs?: string[]; counts?: Record<string, number>; workspace?: string; workspaceMeta?: string; nav?: NavItem[]; topActions?: React.ReactNode; overlay?: React.ReactNode; sideFoot?: React.ReactNode; search?: boolean; children?: React.ReactNode; style?: React.CSSProperties }
export declare function AppShell(props: AppShellProps): React.ReactElement;

/** Formatting only: U+2212 minus, fixed decimals, optional explicit sign. */
export declare const format: { num(v: number | null, digits?: number, sign?: boolean): string; pct(v: number | null, digits?: number, sign?: boolean): string };
/** Seeded synthetic data for previews and empty-state demos. Illustrative, never a research result. */
export declare const sample: { rng(seed: number): () => number; series(seed: number, n: number, mu: number, sigma: number, start?: number, regimes?: Array<{ from: number; to: number; mu: number; sigma: number }>): number[]; draws(seed: number, n: number, mu: number, sd: number): number[] };

declare global { interface Window { QuantForge: typeof import('./index') } }
