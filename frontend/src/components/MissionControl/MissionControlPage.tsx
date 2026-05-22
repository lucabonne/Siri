import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Brain,
  CheckCircle2,
  Circle,
  Clock3,
  Cpu,
  Database,
  FolderGit2,
  LockKeyhole,
  Pin,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react';
import {
  missionAgents,
  missionFeed,
  missionMemories,
  missionMetrics,
  missionProjects,
  missionSections,
  missionTasks,
  permissionEvents,
  quickCommands,
  researchItems,
  settingsItems,
  terminalSignals,
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

function StatusPill({ tone, children }: { tone: StatusTone; children: ReactNode }) {
  const style = toneStyle(tone);
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-md border px-2 py-1 text-xs font-medium"
      style={{ background: style.bg, borderColor: style.border, color: style.text }}
    >
      {children}
    </span>
  );
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
      aria-label="Mission Control sections"
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

function MetricGrid() {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {missionMetrics.map((metric) => (
        <ShellPanel key={metric.label} title={metric.label}>
          <div className="flex min-h-24 flex-col justify-between gap-3">
            <div className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>
              {metric.value}
            </div>
            <div className="flex items-end justify-between gap-3">
              <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {metric.detail}
              </p>
              <StatusPill tone={metric.tone}>{metric.tone}</StatusPill>
            </div>
          </div>
        </ShellPanel>
      ))}
    </div>
  );
}

function KeyValue({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 border-b py-3 last:border-b-0" style={{ borderColor: 'var(--color-border)' }}>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md" style={{ background: 'var(--color-bg-secondary)', color: 'var(--color-accent)' }}>
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          {label}
        </div>
        <div className="truncate text-sm font-medium" style={{ color: 'var(--color-text)' }}>
          {value}
        </div>
      </div>
    </div>
  );
}

function HomeSection() {
  return (
    <div className="grid gap-4">
      <MetricGrid />
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <ShellPanel title="Morning Briefing" action="local preview">
          <div className="grid gap-3">
            {missionFeed.slice(0, 3).map((item) => (
              <div key={`${item.time}-${item.title}`} className="grid gap-2 border-b pb-3 last:border-b-0 last:pb-0" style={{ borderColor: 'var(--color-border)' }}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                      {item.time}
                    </div>
                    <div className="mt-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                      {item.title}
                    </div>
                  </div>
                  <StatusPill tone={item.tone}>{item.tone}</StatusPill>
                </div>
                <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  {item.detail}
                </p>
              </div>
            ))}
          </div>
        </ShellPanel>

        <ShellPanel title="Quick Commands" action="inactive">
          <div className="grid gap-2">
            {quickCommands.map((command) => {
              const Icon = command.icon;
              return (
                <button
                  key={command.label}
                  type="button"
                  className="flex h-11 items-center justify-between rounded-md border px-3 text-left text-sm transition-colors"
                  style={{
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text)',
                    background: 'var(--color-bg-secondary)',
                  }}
                >
                  <span className="flex items-center gap-3 font-medium">
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
    </div>
  );
}

function TodaySection() {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <ShellPanel title="Today">
        <div className="space-y-3">
          {missionFeed.map((item) => (
            <div key={`${item.time}-${item.title}`} className="grid grid-cols-[64px_1fr_auto] items-start gap-3 border-b pb-3 last:border-b-0 last:pb-0" style={{ borderColor: 'var(--color-border)' }}>
              <span className="font-mono text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {item.time}
              </span>
              <div className="min-w-0">
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

      <ShellPanel title="System Status">
        <KeyValue icon={<ShieldCheck size={15} />} label="Privacy posture" value="Local-first, backend wiring deferred" />
        <KeyValue icon={<Database size={15} />} label="Memory" value="SQLite and vector layers planned" />
        <KeyValue icon={<Clock3 size={15} />} label="Briefing cadence" value="Morning review surface" />
        <KeyValue icon={<Cpu size={15} />} label="Mode" value="Focus" />
      </ShellPanel>
    </div>
  );
}

function WorldMapSection() {
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <ShellPanel title="World Map" action="signal board">
        <div
          className="relative min-h-[360px] overflow-hidden rounded-md border"
          style={{
            borderColor: 'var(--color-border)',
            background:
              'linear-gradient(135deg, color-mix(in srgb, var(--color-bg-secondary) 86%, transparent), var(--color-surface))',
          }}
        >
          <div className="absolute inset-8 rounded-[48%]" style={{ border: '1px solid var(--color-border)' }} />
          <div className="absolute inset-x-8 top-1/2 h-px" style={{ background: 'var(--color-border)' }} />
          <div className="absolute inset-y-8 left-1/2 w-px" style={{ background: 'var(--color-border)' }} />
          {worldSignals.map((signal) => {
            const style = toneStyle(signal.tone);
            return (
              <div key={signal.city} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: signal.x, top: signal.y }}>
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

      <ShellPanel title="Signals">
        <div className="space-y-3">
          {worldSignals.map((signal) => (
            <div key={signal.city} className="flex items-center justify-between gap-3 border-b pb-3 last:border-b-0 last:pb-0" style={{ borderColor: 'var(--color-border)' }}>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {signal.city}
                </div>
                <div className="truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {signal.label}
                </div>
              </div>
              <StatusPill tone={signal.tone}>{signal.tone}</StatusPill>
            </div>
          ))}
        </div>
      </ShellPanel>
    </div>
  );
}

function TasksSection() {
  return (
    <ShellPanel title="Tasks">
      <div className="grid gap-3">
        {missionTasks.map((task) => (
          <div key={task.title} className="grid gap-3 border-b pb-3 last:border-b-0 last:pb-0 md:grid-cols-[1fr_150px_110px_90px_auto]" style={{ borderColor: 'var(--color-border)' }}>
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
            <StatusPill tone={task.tone}>{task.tone}</StatusPill>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function AgentsSection() {
  return (
    <ShellPanel title="Agents" action="workspace">
      <div className="grid gap-4 md:grid-cols-2">
        {missionAgents.map((agent) => (
          <div key={agent.name} className="border-b pb-4 last:border-b-0 md:border-b-0" style={{ borderColor: 'var(--color-border)' }}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {agent.name}
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {agent.role}
                </div>
              </div>
              <StatusPill tone={agent.tone}>{agent.status}</StatusPill>
            </div>
            <div className="mt-4 h-2 rounded-full" style={{ background: 'var(--color-bg-tertiary)' }}>
              <div className="h-2 rounded-full" style={{ width: `${agent.load}%`, background: toneStyle(agent.tone).text }} />
            </div>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function MemorySection() {
  const pinnedCount = useMemo(
    () => missionMemories.filter((memory) => memory.pinned).length,
    [],
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
      <ShellPanel title="Memory Layer">
        <KeyValue icon={<Pin size={15} />} label="Pinned memories" value={String(pinnedCount)} />
        <KeyValue icon={<Brain size={15} />} label="Second Brain" value="Notes, backlinks, citations" />
        <KeyValue icon={<Database size={15} />} label="Export target" value="Markdown, YAML, wikilinks" />
      </ShellPanel>

      <ShellPanel title="Recent Memories">
        <div className="space-y-3">
          {missionMemories.map((memory) => (
            <div key={memory.title} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b pb-3 last:border-b-0 last:pb-0" style={{ borderColor: 'var(--color-border)' }}>
              <Circle size={10} style={{ color: memory.pinned ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }} />
              <div className="min-w-0">
                <div className="truncate text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                  {memory.title}
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  <span>{memory.type}</span>
                  {memory.tags.map((tag) => (
                    <span key={tag}>#{tag}</span>
                  ))}
                </div>
              </div>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {memory.age}
              </span>
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
      <div className="grid gap-4 md:grid-cols-3">
        {missionProjects.map((project) => (
          <div key={project.name} className="min-w-0">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {project.name}
                </div>
                <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {project.status}
                </div>
              </div>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {project.progress}%
              </span>
            </div>
            <div className="mt-4 h-2 rounded-full" style={{ background: 'var(--color-bg-tertiary)' }}>
              <div className="h-2 rounded-full" style={{ width: `${project.progress}%`, background: 'var(--color-accent)' }} />
            </div>
            <div className="mt-3 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              Next: {project.next}
            </div>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function TerminalSection() {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <ShellPanel title="Terminal">
        <div
          className="rounded-md border p-4 font-mono text-sm"
          style={{
            borderColor: 'var(--color-border)',
            background: 'var(--color-code-bg)',
            color: 'var(--color-text)',
          }}
        >
          <div style={{ color: 'var(--color-text-tertiary)' }}>$ npm run build</div>
          <pre className="mt-3 whitespace-pre-wrap text-xs leading-5">
            Phase 1 shell uses mock data only.
            {'\n'}Backend command execution remains deferred.
          </pre>
        </div>
      </ShellPanel>

      <ShellPanel title="Terminal Signals">
        <div className="space-y-3">
          {terminalSignals.map((signal) => (
            <div key={signal.command} className="border-b pb-3 last:border-b-0 last:pb-0" style={{ borderColor: 'var(--color-border)' }}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm" style={{ color: 'var(--color-text)' }}>
                    {signal.command}
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {signal.detail}
                  </div>
                </div>
                <StatusPill tone={signal.tone}>{signal.status}</StatusPill>
              </div>
            </div>
          ))}
        </div>
      </ShellPanel>
    </div>
  );
}

function ResearchSection() {
  return (
    <ShellPanel title="Research">
      <div className="grid gap-3">
        {researchItems.map((item) => (
          <div key={item.title} className="grid gap-3 border-b pb-3 last:border-b-0 last:pb-0 md:grid-cols-[1fr_140px_100px_auto]" style={{ borderColor: 'var(--color-border)' }}>
            <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              {item.title}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {item.status}
            </span>
            <span className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
              {item.sources} sources
            </span>
            <StatusPill tone={item.tone}>{item.tone}</StatusPill>
          </div>
        ))}
      </div>
    </ShellPanel>
  );
}

function SettingsSection() {
  return (
    <ShellPanel title="Settings">
      <div className="grid gap-3 md:grid-cols-2">
        {settingsItems.map((item) => (
          <KeyValue key={item.label} icon={<LockKeyhole size={15} />} label={item.label} value={item.value} />
        ))}
      </div>
    </ShellPanel>
  );
}

function PermissionsSection() {
  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Permission Levels">
        <div className="space-y-3">
          {permissionEvents.map((event) => (
            <div key={event.level} className="border-b pb-3 last:border-b-0 last:pb-0" style={{ borderColor: 'var(--color-border)' }}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                    {event.level} - {event.label}
                  </div>
                  <p className="mt-1 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                    {event.detail}
                  </p>
                </div>
                <StatusPill tone={event.tone}>{event.tone}</StatusPill>
              </div>
            </div>
          ))}
        </div>
      </ShellPanel>

      <ShellPanel title="Approval Queue">
        <KeyValue icon={<ShieldCheck size={15} />} label="Safe reads" value="Allowed at Level 0" />
        <KeyValue icon={<Activity size={15} />} label="Safe actions" value="Declared at Level 1" />
        <KeyValue icon={<AlertTriangle size={15} />} label="Execution" value="Confirmed at Level 2" />
        <KeyValue icon={<LockKeyhole size={15} />} label="Dangerous commands" value="Blocked at Level 3" />
      </ShellPanel>
    </div>
  );
}

function ActiveSection({ active }: { active: MissionSectionId }) {
  switch (active) {
    case 'home':
      return <HomeSection />;
    case 'today':
      return <TodaySection />;
    case 'world-map':
      return <WorldMapSection />;
    case 'tasks':
      return <TasksSection />;
    case 'agents':
      return <AgentsSection />;
    case 'memory':
      return <MemorySection />;
    case 'projects':
      return <ProjectsSection />;
    case 'terminal':
      return <TerminalSection />;
    case 'research':
      return <ResearchSection />;
    case 'settings':
      return <SettingsSection />;
    case 'permissions':
      return <PermissionsSection />;
    default:
      return <HomeSection />;
  }
}

export function MissionControlPage() {
  const [activeSection, setActiveSection] = useState<MissionSectionId>('home');

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header
        className="border-b px-4 py-4 md:px-6"
        style={{
          borderColor: 'var(--color-border)',
          background: 'color-mix(in srgb, var(--color-bg) 86%, transparent)',
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border"
                style={{
                  borderColor: 'var(--color-border)',
                  background: 'var(--color-accent-subtle)',
                  color: 'var(--color-accent)',
                }}
              >
                <TerminalSquare size={20} />
              </span>
              <div className="min-w-0">
                <p className="text-xs uppercase" style={{ color: 'var(--color-text-tertiary)' }}>
                  Siri
                </p>
                <h1 className="truncate text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>
                  Mission Control
                </h1>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone="good">Focus mode</StatusPill>
            <StatusPill tone="busy">Siri project</StatusPill>
            <StatusPill tone="quiet">Mock data</StatusPill>
          </div>
        </div>
      </header>

      <MissionTabs active={activeSection} onChange={setActiveSection} />

      <main className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
          <ShellPanel title="Operating Snapshot" action="phase 1">
            <div className="grid gap-3 md:grid-cols-4">
              <KeyValue icon={<CheckCircle2 size={15} />} label="Mode" value="Focus" />
              <KeyValue icon={<FolderGit2 size={15} />} label="Project" value="Siri Mission Control" />
              <KeyValue icon={<Brain size={15} />} label="Memory" value="Second Brain planned" />
              <KeyValue icon={<LockKeyhole size={15} />} label="Permissions" value="Levels 0-3 next" />
            </div>
          </ShellPanel>

          <ActiveSection active={activeSection} />
        </div>
      </main>
    </div>
  );
}
