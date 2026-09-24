import { api } from './api';
import './app.css';
import { QF, type NavItem } from './design-system';
import { useResource } from './resource';
import { href, useRoute } from './route';
import { HypothesisScreen } from './screens/HypothesisScreen';
import { RegistryScreen } from './screens/RegistryScreen';

const NAV: NavItem[] = [
  { group: 'Research' },
  { key: 'registry', label: 'Hypothesis registry', icon: 'registry', href: href.registry },
];

export function App() {
  const route = useRoute();
  const health = useResource('health', api.health);
  const meta =
    health.state !== 'ready'
      ? 'Read-only'
      : health.data.exists
        ? `Read-only · schema v${health.data.schemaVersion ?? '—'}`
        : 'No results store yet';
  return (
    <QF.AppShell
      active="registry"
      nav={NAV}
      search={false}
      workspace="Results store"
      workspaceMeta={meta}
      crumbs={
        route.screen === 'registry'
          ? ['Results store', 'Hypothesis registry']
          : ['Results store', 'Hypothesis registry', route.id]
      }
      style={{ minHeight: '100vh' }}
    >
      {route.screen === 'registry' ? <RegistryScreen /> : <HypothesisScreen key={route.id} id={route.id} />}
    </QF.AppShell>
  );
}
