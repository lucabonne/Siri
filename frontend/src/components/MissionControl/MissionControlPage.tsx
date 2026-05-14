import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  ArrowUpRight,
  Ban,
  CheckCircle2,
  Circle,
  Clock3,
  Gauge,
  LockKeyhole,
  Pin,
  Plus,
  Radar,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  XCircle,
} from 'lucide-react';
import {
  createMemory,
  decideSecurityApproval,
  deleteMemory,
  fetchPermissionAudit,
  fetchSecurityApprovals,
  listWorkspaceAgents,
  listMemories,
  searchMemory,
  setMemoryPinned,
  switchActiveWorkspaceAgent,
} from '../../lib/api';
import type {
  MemorySearchResult,
  StructuredMemory,
  WorkspaceAgentConfig,
} from '../../lib/api';
import {
  approvalQueue,
  missionAgents,
  missionFeed,
  missionMemories,
  missionMetrics,
  missionProjects,
  missionSections,
  missionTasks,
  permissionEvents,
  quickCommands,
  worldSignals,
} from './mockData';
import type {
  ApprovalRecord,
  MissionMemory,
  MissionSectionId,
  PermissionEvent,
  StatusTone,
} from './types';

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

function toFallbackWorkspaceAgents(): WorkspaceAgentConfig[] {
  return missionAgents.map((agent) => {
    const id = agent.role.toLowerCase();
    return {
      id,
      display_name: agent.name,
      description: `${agent.role} agent: ${agent.status}`,
      allowed_tools: [],
      memory_scope: [],
      permission_ceiling: 'READ_ONLY',
      preferred_model: 'mock',
      personality_mode: agent.role,
      output_style: 'Mock fallback',
      routing: {
        task_classification: [id],
        recommended_agent: id,
        fallback_agent: 'coding',
        multi_agent_compatibility: [],
      },
    };
  });
}

function AgentsSection() {
  const [agents, setAgents] = useState<WorkspaceAgentConfig[]>(toFallbackWorkspaceAgents);
  const [activeAgentId, setActiveAgentId] = useState<string>('');
  const [backendLive, setBackendLive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [switchingAgentId, setSwitchingAgentId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    listWorkspaceAgents()
      .then((data) => {
        if (cancelled) return;
        setAgents(data.agents);
        setActiveAgentId(data.active_agent_id);
        setBackendLive(true);
      })
      .catch(() => {
        if (cancelled) return;
        setAgents(toFallbackWorkspaceAgents());
        setActiveAgentId('');
        setBackendLive(false);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const switchAgent = async (agentId: string) => {
    if (!backendLive || agentId === activeAgentId) return;
    setSwitchingAgentId(agentId);
    try {
      const state = await switchActiveWorkspaceAgent(agentId);
      setActiveAgentId(state.active_agent_id);
    } finally {
      setSwitchingAgentId(null);
    }
  };

  return (
    <ShellPanel
      title="Agents"
      action={backendLive ? 'Live registry' : isLoading ? 'Loading' : 'Mock fallback'}
    >
      <div className="grid gap-3 md:grid-cols-2">
        {agents.map((agent) => {
          const isActive = agent.id === activeAgentId;
          const toolPreview = agent.allowed_tools.slice(0, 4).join(', ');
          return (
          <div
            key={agent.id}
            className="rounded-md border p-4"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {agent.display_name}
                </div>
                <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {agent.personality_mode}
                </div>
              </div>
              <StatusPill tone={isActive ? 'good' : 'quiet'}>
                {isActive ? 'Active' : agent.permission_ceiling}
              </StatusPill>
            </div>
            <p className="mt-3 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {agent.description}
            </p>
            <div className="mt-3 grid gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              <span>Model: {agent.preferred_model || 'default'}</span>
              <span>Memory: {agent.memory_scope.join(', ') || 'none declared'}</span>
              <span>Tools: {toolPreview || 'chat-only'}{agent.allowed_tools.length > 4 ? '...' : ''}</span>
            </div>
            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                Route: {agent.routing.task_classification.slice(0, 2).join(', ')}
              </span>
              {backendLive && (
                <button
                  type="button"
                  disabled={isActive || switchingAgentId === agent.id}
                  onClick={() => switchAgent(agent.id)}
                  className="rounded-md border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                  style={{
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text)',
                    background: isActive ? 'var(--color-bg-tertiary)' : 'var(--color-bg)',
                  }}
                >
                  {isActive ? 'Selected' : switchingAgentId === agent.id ? 'Switching' : 'Switch'}
                </button>
              )}
            </div>
          </div>
          );
        })}
      </div>
    </ShellPanel>
  );
}

function toMissionMemory(memory: StructuredMemory | MemorySearchResult): MissionMemory {
  return {
    id: memory.id ?? `${memory.content}-${memory.created_at ?? ''}`,
    content: memory.content,
    memory_type: memory.memory_type ?? 'note',
    tags: memory.tags ?? [],
    pinned: Boolean(memory.pinned),
    created_at: memory.created_at ?? new Date().toISOString(),
    source: memory.source
      ? {
          title: memory.source.title,
          url: memory.source.url,
        }
      : null,
  };
}

function MemorySection() {
  const [memories, setMemories] = useState<MissionMemory[]>(missionMemories);
  const [query, setQuery] = useState('');
  const [draft, setDraft] = useState('');
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadMemories = async () => {
    try {
      const items = await listMemories({ limit: 12 });
      setMemories(items.map(toMissionMemory));
      setLive(true);
    } catch {
      setMemories(missionMemories);
      setLive(false);
    }
  };

  useEffect(() => {
    loadMemories();
  }, []);

  const filteredCounts = useMemo(() => {
    const byType = new Map<string, number>();
    memories.forEach((memory) => {
      byType.set(memory.memory_type, (byType.get(memory.memory_type) ?? 0) + 1);
    });
    return [
      ['Pinned', memories.filter((memory) => memory.pinned).length],
      ['Notes', byType.get('note') ?? 0],
      ['Decisions', byType.get('decision') ?? 0],
      ['Sources', memories.filter((memory) => memory.source?.url).length],
    ];
  }, [memories]);

  const runSearch = async () => {
    if (!query.trim()) {
      await loadMemories();
      return;
    }
    try {
      const results = await searchMemory(query, 12);
      setMemories(results.map(toMissionMemory));
      setLive(true);
    } catch {
      const lower = query.toLowerCase();
      setMemories((items) =>
        items.filter((memory) => memory.content.toLowerCase().includes(lower)),
      );
      setLive(false);
    }
  };

  const addMemory = async () => {
    if (!draft.trim()) return;
    setBusy(true);
    try {
      const memory = await createMemory({
        content: draft.trim(),
        memory_type: 'note',
        tags: ['mission-control'],
      });
      setMemories((items) => [toMissionMemory(memory), ...items]);
      setDraft('');
      setLive(true);
    } catch {
      const fallback = {
        id: `local-${Date.now()}`,
        content: draft.trim(),
        memory_type: 'note',
        tags: ['mission-control'],
        pinned: false,
        created_at: new Date().toISOString(),
        source: null,
      };
      setMemories((items) => [fallback, ...items]);
      setDraft('');
      setLive(false);
    } finally {
      setBusy(false);
    }
  };

  const togglePin = async (memory: MissionMemory) => {
    if (!live || memory.id.startsWith('mock-') || memory.id.startsWith('local-')) {
      setMemories((items) =>
        items.map((item) => (item.id === memory.id ? { ...item, pinned: !item.pinned } : item)),
      );
      return;
    }
    try {
      const updated = await setMemoryPinned(memory.id, !memory.pinned);
      setMemories((items) =>
        items.map((item) => (item.id === memory.id ? toMissionMemory(updated) : item)),
      );
    } catch {
      setLive(false);
    }
  };

  const removeMemory = async (memory: MissionMemory) => {
    if (live && !memory.id.startsWith('mock-') && !memory.id.startsWith('local-')) {
      try {
        await deleteMemory(memory.id);
      } catch {
        setLive(false);
      }
    }
    setMemories((items) => items.filter((item) => item.id !== memory.id));
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Memory" action={live ? 'live' : 'mock'}>
        <div className="grid grid-cols-2 gap-3">
          {filteredCounts.map(([label, value]) => (
            <div
              key={label}
              className="rounded-md border p-4"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>
                {value}
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {label}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 grid gap-2">
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') runSearch();
              }}
              placeholder="Search memory"
              className="min-w-0 flex-1 rounded-md border px-3 py-2 text-sm outline-none"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
                background: 'var(--color-bg-secondary)',
              }}
            />
            <button
              type="button"
              onClick={runSearch}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
              title="Search"
            >
              <Search size={16} />
            </button>
          </div>
          <div className="flex gap-2">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') addMemory();
              }}
              placeholder="Create memory"
              className="min-w-0 flex-1 rounded-md border px-3 py-2 text-sm outline-none"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
                background: 'var(--color-bg-secondary)',
              }}
            />
            <button
              type="button"
              onClick={addMemory}
              disabled={busy}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md border disabled:opacity-60"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
              title="Add"
            >
              <Plus size={16} />
            </button>
          </div>
        </div>
      </ShellPanel>
      <ShellPanel title="Recent recalls">
        <div className="space-y-2">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 rounded-md border px-3 py-3 text-sm"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            >
              <Circle size={10} style={{ color: 'var(--color-accent)' }} />
              <div className="min-w-0">
                <div className="truncate">{memory.content}</div>
                <div className="mt-1 flex gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  <span>{memory.memory_type}</span>
                  {memory.source?.title && <span>{memory.source.title}</span>}
                </div>
              </div>
              <button
                type="button"
                onClick={() => togglePin(memory)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md"
                style={{ color: memory.pinned ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}
                title={memory.pinned ? 'Unpin' : 'Pin'}
              >
                <Pin size={15} />
              </button>
              <button
                type="button"
                onClick={() => removeMemory(memory)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md"
                style={{ color: 'var(--color-text-tertiary)' }}
                title="Delete"
              >
                <Trash2 size={15} />
              </button>
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

function formatEventTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function auditActionLabel(action: string): PermissionEvent['action'] {
  if (action === 'allow') return 'Allowed';
  if (action === 'deny') return 'Blocked';
  return 'Needs approval';
}

function actionTone(action: PermissionEvent['action']): StatusTone {
  if (action === 'Allowed') return 'good';
  if (action === 'Blocked') return 'watch';
  return 'busy';
}

function PermissionsSection() {
  const [approvals, setApprovals] = useState<ApprovalRecord[]>(approvalQueue);
  const [events, setEvents] = useState<PermissionEvent[]>(permissionEvents);
  const [status, setStatus] = useState<'ready' | 'loading' | 'offline'>('loading');
  const [actingId, setActingId] = useState<string>('');

  const refreshPermissions = async () => {
    setStatus('loading');
    try {
      const [approvalData, auditData] = await Promise.all([
        fetchSecurityApprovals('pending', 50),
        fetchPermissionAudit(50),
      ]);
      setApprovals(approvalData);
      setEvents(
        auditData.map((event) => ({
          tool: event.tool,
          action: auditActionLabel(event.action),
          source: String(event.request_metadata?.source || 'tool_executor'),
          time: formatEventTime(event.timestamp),
          reason: event.reason,
        })),
      );
      setStatus('ready');
    } catch {
      setApprovals(approvalQueue);
      setEvents(permissionEvents);
      setStatus('offline');
    }
  };

  useEffect(() => {
    refreshPermissions();
  }, []);

  const decide = async (approvalId: string, decision: 'approve' | 'deny') => {
    setActingId(approvalId);
    try {
      await decideSecurityApproval(approvalId, decision);
      setApprovals((current) => current.filter((approval) => approval.id !== approvalId));
      setStatus('ready');
    } catch {
      setStatus('offline');
    } finally {
      setActingId('');
    }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <ShellPanel
        title="Approval Queue"
        action={status === 'offline' ? 'mock fallback' : `${approvals.length} pending`}
      >
        <div className="space-y-3">
          {approvals.length === 0 ? (
            <div
              className="flex items-center gap-3 rounded-md border p-4 text-sm"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
            >
              <ShieldCheck size={18} style={{ color: 'var(--color-success)' }} />
              No pending approvals
            </div>
          ) : (
            approvals.map((approval) => (
              <div
                key={approval.id}
                className="rounded-md border p-4"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                        {approval.tool}
                      </span>
                      <StatusPill tone="watch">{approval.level.replace('_', ' ')}</StatusPill>
                    </div>
                    <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                      {approval.reason}
                    </p>
                    {approval.command_preview && (
                      <div
                        className="mt-3 overflow-hidden rounded-md border px-3 py-2 font-mono text-xs"
                        style={{
                          borderColor: 'var(--color-border)',
                          background: 'var(--color-code-bg)',
                          color: 'var(--color-text)',
                        }}
                      >
                        {approval.command_preview}
                      </div>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                      <span>{approval.source || 'tool_executor'}</span>
                      <span>{formatEventTime(approval.requested_at)}</span>
                      {approval.agent_id && <span>{approval.agent_id}</span>}
                      {approval.argument_keys.length > 0 && <span>{approval.argument_keys.join(', ')}</span>}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      disabled={actingId === approval.id}
                      onClick={() => decide(approval.id, 'approve')}
                      className="flex h-9 w-9 items-center justify-center rounded-md border transition-colors disabled:opacity-60"
                      style={{
                        borderColor: 'color-mix(in srgb, var(--color-success) 35%, transparent)',
                        color: 'var(--color-success)',
                        background: 'color-mix(in srgb, var(--color-success) 10%, transparent)',
                      }}
                      title="Approve"
                    >
                      <CheckCircle2 size={17} />
                    </button>
                    <button
                      type="button"
                      disabled={actingId === approval.id}
                      onClick={() => decide(approval.id, 'deny')}
                      className="flex h-9 w-9 items-center justify-center rounded-md border transition-colors disabled:opacity-60"
                      style={{
                        borderColor: 'color-mix(in srgb, var(--color-error) 35%, transparent)',
                        color: 'var(--color-error)',
                        background: 'color-mix(in srgb, var(--color-error) 10%, transparent)',
                      }}
                      title="Deny"
                    >
                      <XCircle size={17} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </ShellPanel>

      <ShellPanel
        title="Permission Audit"
        action={status === 'loading' ? 'loading' : status === 'offline' ? 'offline' : 'live'}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <StatusPill tone={status === 'ready' ? 'good' : status === 'loading' ? 'busy' : 'quiet'}>
            {status}
          </StatusPill>
          <button
            type="button"
            onClick={refreshPermissions}
            className="flex h-9 w-9 items-center justify-center rounded-md border transition-colors"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
              background: 'var(--color-bg-secondary)',
            }}
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        </div>
        <div className="space-y-2">
          {events.map((event) => (
            <div
              key={`${event.tool}-${event.time}-${event.action}`}
              className="grid gap-2 rounded-md border p-3"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                  {event.tool}
                </span>
                <StatusPill tone={actionTone(event.action)}>
                  {event.action === 'Blocked' ? <Ban size={12} className="mr-1" /> : null}
                  {event.action}
                </StatusPill>
              </div>
              <div className="flex flex-wrap gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                <span>{event.source}</span>
                <span>{event.time}</span>
              </div>
              {event.reason && (
                <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {event.reason}
                </p>
              )}
            </div>
          ))}
        </div>
      </ShellPanel>
    </div>
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
