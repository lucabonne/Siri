import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  Circle,
  Clock3,
  Gauge,
  LockKeyhole,
  Radar,
  ShieldAlert,
} from 'lucide-react';
import {
  missionAgents,
  missionFeed,
  missionMetrics,
  missionProjects,
  missionSections,
  missionTasks,
  permissionEvents,
  quickCommands,
  worldSignals,
} from './mockData';
import type { MissionSectionId, StatusTone } from './types';

const toneStyles: Record<StatusTone, { bg: string; text: string; border: string }> = {
  good: {
    bg: 'color-mix(in srgb, var(--color-success) 12%, transparent)',
    text: 'var(--color-success)',
    border: 'color-mix(in srgb, var(--color-success) 28%, transparent)',
  },
  watch: {
    bg: 'color-mix(in srgb, var(--color-warning) 14%, transparent)',
    text: 'var(--color-warning)',
    border: 'color-mix(in srgb, var(--color-warning) 30%, transparent)',
  },
  busy: {
    bg: 'var(--color-accent-subtle)',
    text: 'var(--color-accent)',
    border: 'color-mix(in srgb, var(--color-accent) 28%, transparent)',
  },
  quiet: {
    bg: 'var(--color-bg-secondary)',
    text: 'var(--color-text-secondary)',
    border: 'var(--color-border)',
  },
};

function toneStyle(tone: StatusTone) {
  return toneStyles[tone];
}

function ShellPanel({
  title,
  action,
  children,
}: {
  title: string;
  action?: string;
  children: ReactNode;
}) {
  return (
    <section className="hud-panel p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          {title}
        </h2>
        {action && (
          <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            {action}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function StatusPill({ tone, children }: { tone: StatusTone; children: ReactNode }) {
  const style = toneStyle(tone);
  return (
    <span
      className="inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium"
      style={{ background: style.bg, borderColor: style.border, color: style.text }}
    >
      {children}
    </span>
  );
}

function MissionTabs({
  active,
  onChange,
}: {
  active: MissionSectionId;
  onChange: (section: MissionSectionId) => void;
}) {
  return (
    <nav
      className="flex gap-1 overflow-x-auto border-b px-4"
      style={{ borderColor: 'var(--color-border)' }}
    >
      {missionSections.map((section) => {
        const Icon = section.icon;
        const selected = section.id === active;
        return (
          <button
            key={section.id}
            type="button"
            onClick={() => onChange(section.id)}
            className="flex h-11 shrink-0 items-center gap-2 border-b-2 px-3 text-sm transition-colors"
            style={{
              borderColor: selected ? 'var(--color-accent)' : 'transparent',
              color: selected ? 'var(--color-text)' : 'var(--color-text-secondary)',
              background: selected ? 'var(--color-accent-subtle)' : 'transparent',
            }}
          >
            <Icon size={16} style={selected ? { color: 'var(--color-accent)' } : undefined} />
            <span>{section.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function HomeSection() {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.4fr_0.9fr]">
      <div className="grid gap-4 md:grid-cols-2">
        {missionMetrics.map((metric) => (
          <ShellPanel key={metric.label} title={metric.label}>
            <div className="flex items-end justify-between gap-4">
              <div>
                <div className="text-3xl font-semibold" style={{ color: 'var(--color-text)' }}>
                  {metric.value}
                </div>
                <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  {metric.detail}
                </p>
              </div>
              <StatusPill tone={metric.tone}>{metric.tone}</StatusPill>
            </div>
          </ShellPanel>
        ))}
      </div>
      <ShellPanel title="Command lane" action="mock">
        <div className="grid gap-2">
          {quickCommands.map((command) => {
            const Icon = command.icon;
            return (
              <button
                key={command.label}
                type="button"
                className="flex items-center justify-between rounded-md border px-3 py-3 text-left transition-colors"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text)',
                  background: 'var(--color-bg-secondary)',
                }}
              >
                <span className="flex items-center gap-3 text-sm font-medium">
                  <Icon size={16} style={{ color: 'var(--color-accent)' }} />
                  {command.label}
                </span>
                <ArrowUpRight size={15} style={{ color: 'var(--color-text-tertiary)' }} />
              </button>
            );
          })}
        </div>
      </ShellPanel>
    </div>
  );
}

function TodaySection() {
  return (
    <ShellPanel title="Today">
      <div className="space-y-3">
        {missionFeed.map((item) => (
          <div
            key={`${item.time}-${item.title}`}
            className="grid grid-cols-[64px_1fr_auto] items-start gap-3 rounded-md border p-3"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <span className="font-mono text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {item.time}
            </span>
            <div>
              <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                {item.title}
              </div>
              <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {item.detail}
              </p>
            </div>
            <StatusPill tone={item.tone}>{item.tone}</StatusPill>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function WorldMapSection() {
  return (
    <ShellPanel title="World Map" action="signals">
      <div
        className="relative min-h-[340px] overflow-hidden rounded-md border"
        style={{
          borderColor: 'var(--color-border)',
          background:
            'linear-gradient(135deg, color-mix(in srgb, var(--color-bg-secondary) 88%, transparent), var(--color-surface))',
        }}
      >
        <div
          className="absolute inset-6 rounded-[50%]"
          style={{
            border: '1px solid var(--color-border)',
            background:
              'radial-gradient(circle at center, color-mix(in srgb, var(--color-accent) 10%, transparent), transparent 62%)',
          }}
        />
        <div
          className="absolute inset-x-8 top-1/2 h-px"
          style={{ background: 'var(--color-border)' }}
        />
        <div
          className="absolute inset-y-8 left-1/2 w-px"
          style={{ background: 'var(--color-border)' }}
        />
        {worldSignals.map((signal) => {
          const style = toneStyle(signal.tone);
          return (
            <div
              key={signal.city}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: signal.x, top: signal.y }}
            >
              <div
                className="h-3 w-3 rounded-full border"
                style={{
                  background: style.text,
                  borderColor: 'var(--color-surface)',
                  boxShadow: `0 0 0 6px ${style.bg}`,
                }}
              />
              <div
                className="mt-3 min-w-32 rounded-md border px-3 py-2 text-xs"
                style={{
                  background: 'var(--color-surface)',
                  borderColor: style.border,
                  color: 'var(--color-text)',
                }}
              >
                <div className="font-semibold">{signal.city}</div>
                <div className="mt-1" style={{ color: 'var(--color-text-secondary)' }}>
                  {signal.label}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </ShellPanel>
  );
}

function TasksSection() {
  return (
    <ShellPanel title="Tasks">
      <div className="grid gap-3">
        {missionTasks.map((task) => (
          <div
            key={task.title}
            className="grid gap-3 rounded-md border p-3 md:grid-cols-[1fr_140px_110px_90px]"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              {task.title}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {task.owner}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {task.state}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
              {task.due}
            </span>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function AgentsSection() {
  return (
    <ShellPanel title="Agents">
      <div className="grid gap-3 md:grid-cols-2">
        {missionAgents.map((agent) => (
          <div
            key={agent.name}
            className="rounded-md border p-4"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {agent.name}
                </div>
                <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {agent.role}
                </div>
              </div>
              <StatusPill tone={agent.status.includes('Awaiting') ? 'watch' : 'good'}>
                {agent.status}
              </StatusPill>
            </div>
            <div className="mt-4 h-2 rounded-full" style={{ background: 'var(--color-bg-tertiary)' }}>
              <div
                className="h-2 rounded-full"
                style={{ width: `${agent.load}%`, background: 'var(--color-accent)' }}
              />
            </div>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function MemorySection() {
  return (
    <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Memory">
        <div className="grid grid-cols-2 gap-3">
          {['People', 'Places', 'Decisions', 'Open loops'].map((label, index) => (
            <div
              key={label}
              className="rounded-md border p-4"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>
                {[128, 42, 317, 19][index]}
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </ShellPanel>
      <ShellPanel title="Recent recalls">
        <div className="space-y-2">
          {['Phase 2 permission notes', 'Desktop source setup', 'Siri branding pass'].map((item) => (
            <div
              key={item}
              className="flex items-center gap-3 rounded-md border px-3 py-3 text-sm"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            >
              <Circle size={10} style={{ color: 'var(--color-accent)' }} />
              {item}
            </div>
          ))}
        </div>
      </ShellPanel>
    </div>
  );
}

function ProjectsSection() {
  return (
    <ShellPanel title="Projects">
      <div className="grid gap-3">
        {missionProjects.map((project) => (
          <div
            key={project.name}
            className="rounded-md border p-4"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {project.name}
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {project.status}
                </div>
              </div>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                Next: {project.next}
              </span>
            </div>
            <div className="mt-4 h-2 rounded-full" style={{ background: 'var(--color-bg-tertiary)' }}>
              <div
                className="h-2 rounded-full"
                style={{ width: `${project.progress}%`, background: 'var(--color-accent)' }}
              />
            </div>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function TerminalSection() {
  return (
    <ShellPanel title="Terminal" action="mock session">
      <div
        className="rounded-md border p-4 font-mono text-sm"
        style={{
          borderColor: 'var(--color-border)',
          background: 'var(--color-code-bg)',
          color: 'var(--color-text)',
        }}
      >
        <div style={{ color: 'var(--color-text-tertiary)' }}>$ siri mission status</div>
        <div className="mt-2">agents: 4 active</div>
        <div>tasks: 7 queued</div>
        <div>permissions: 2 pending approval</div>
        <div className="mt-2" style={{ color: 'var(--color-warning)' }}>
          command gate: waiting
        </div>
      </div>
    </ShellPanel>
  );
}

function ResearchSection() {
  return (
    <ShellPanel title="Research">
      <div className="grid gap-3 md:grid-cols-3">
        {['Local-first agents', 'Permission UX', 'Memory ranking'].map((topic, index) => (
          <div
            key={topic}
            className="rounded-md border p-4"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <FileSearchIcon />
            <div className="mt-3 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              {topic}
            </div>
            <div className="mt-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {[12, 8, 15][index]} sources grouped
            </div>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function FileSearchIcon() {
  return (
    <div
      className="flex h-9 w-9 items-center justify-center rounded-md"
      style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}
    >
      <Radar size={18} />
    </div>
  );
}

function SettingsSection() {
  return (
    <ShellPanel title="Settings">
      <div className="grid gap-3 md:grid-cols-3">
        {[
          ['Model routing', 'Balanced'],
          ['Notifications', 'Priority only'],
          ['Workspace mode', 'Local'],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-md border p-4"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {label}
            </div>
            <div className="mt-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              {value}
            </div>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function PermissionsSection() {
  return (
    <ShellPanel title="Permissions">
      <div className="space-y-3">
        {permissionEvents.map((event) => (
          <div
            key={`${event.tool}-${event.time}`}
            className="grid gap-3 rounded-md border p-3 md:grid-cols-[1fr_150px_160px_70px]"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              {event.tool}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {event.action}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {event.source}
            </span>
            <span className="font-mono text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {event.time}
            </span>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function ActiveSection({ section }: { section: MissionSectionId }) {
  if (section === 'today') return <TodaySection />;
  if (section === 'world-map') return <WorldMapSection />;
  if (section === 'tasks') return <TasksSection />;
  if (section === 'agents') return <AgentsSection />;
  if (section === 'memory') return <MemorySection />;
  if (section === 'projects') return <ProjectsSection />;
  if (section === 'terminal') return <TerminalSection />;
  if (section === 'research') return <ResearchSection />;
  if (section === 'settings') return <SettingsSection />;
  if (section === 'permissions') return <PermissionsSection />;
  return <HomeSection />;
}

export function MissionControlPage() {
  const [activeSection, setActiveSection] = useState<MissionSectionId>('home');
  const activeLabel = useMemo(
    () => missionSections.find((section) => section.id === activeSection)?.label ?? 'Home',
    [activeSection],
  );

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header
          className="mb-4 rounded-md border"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
        >
          <div className="flex flex-col gap-5 p-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-md"
                  style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}
                >
                  <Gauge size={20} />
                </div>
                <div>
                  <div className="text-xs font-medium uppercase" style={{ color: 'var(--color-text-tertiary)' }}>
                    Mission Control
                  </div>
                  <h1 className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>
                    Siri
                  </h1>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <StatusPill tone="good">
                  <CheckCircle2 size={13} className="mr-1" />
                  Local ready
                </StatusPill>
                <StatusPill tone="watch">
                  <ShieldAlert size={13} className="mr-1" />
                  2 approvals
                </StatusPill>
                <StatusPill tone="quiet">
                  <Clock3 size={13} className="mr-1" />
                  10:42 Rome
                </StatusPill>
              </div>
            </div>
            <div
              className="grid min-w-0 gap-3 sm:grid-cols-3"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {[
                ['Current section', activeLabel],
                ['Mode', 'Mock data'],
                ['Surface', 'Dashboard shell'],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="rounded-md border px-4 py-3"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
                >
                  <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    {label}
                  </div>
                  <div className="mt-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                    {value}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <MissionTabs active={activeSection} onChange={setActiveSection} />
        </header>

        <div className="flex-1 pb-8">
          <ActiveSection section={activeSection} />
        </div>

        <footer
          className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t pt-4 text-xs"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-tertiary)' }}
        >
          <span className="flex items-center gap-2">
            <Activity size={14} />
            Siri Mission Control
          </span>
          <span className="flex items-center gap-2">
            <LockKeyhole size={14} />
            No backend changes
          </span>
        </footer>
      </div>
    </div>
  );
}
