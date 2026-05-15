import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  AppWindow,
  ArrowUpRight,
  Ban,
  Brain,
  Camera,
  CheckCircle2,
  Circle,
  Clock3,
  Clipboard,
  Code2,
  Cpu,
  Eye,
  FolderGit2,
  Gauge,
  GitBranch,
  Image,
  LockKeyhole,
  Mic2,
  Package,
  Pin,
  Plus,
  Radar,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Square,
  TerminalSquare,
  Trash2,
  XCircle,
} from 'lucide-react';
import {
  createMemory,
  captureVisionScreenshot,
  decideSecurityApproval,
  deleteMemory,
  fetchCodingPanel,
  fetchBriefingStatus,
  fetchLatestVisualContext,
  fetchLocalContextSnapshot,
  fetchLatestMorningBriefing,
  fetchMorningEvents,
  fetchPermissionAudit,
  fetchRepoSummary,
  fetchRecentVisionScreenshots,
  fetchStartupStatus,
  fetchSecurityApprovals,
  fetchTerminalContext,
  fetchVoicePttStatus,
  fetchWorldEvents,
  fetchWorldMonitorStatus,
  fetchWorldMonitorSyncStatus,
  listWorkspaceAgents,
  listSiriModes,
  listMemories,
  installStartup,
  regenerateMorningBriefing,
  removeStartup,
  requestTerminalCommandApproval,
  searchRepoIndex,
  searchMemory,
  setMemoryPinned,
  startVoicePttRecording,
  switchActiveWorkspaceAgent,
  switchActiveSiriMode,
  triggerStartupMorningBriefing,
  stopVoicePttRecording,
  syncWorldMonitor,
  transcribeLatestVoiceRecording,
} from '../../lib/api';
import type {
  MemorySearchResult,
  LocalContextSnapshot,
  RepoSemanticSearchResult,
  RepoSummaryResponse,
  ScreenshotMetadata,
  SiriModeConfig,
  StructuredMemory,
  TerminalContextSnapshot,
  VisualContext,
  VoicePttStatus,
  WorkspaceAgentConfig,
  CodingPanelSnapshot,
  BriefingStatus,
  DailyBriefing,
  MorningEvent,
  StartupStatus,
  WorldMonitorStatus,
  WorldMonitorSyncStatus,
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

function compactPath(path: string): string {
  if (!path) return 'Unavailable';
  const normalized = path.replace(/\\/g, '/');
  const parts = normalized.split('/').filter(Boolean);
  if (parts.length <= 2) return normalized;
  return `.../${parts.slice(-2).join('/')}`;
}

function basename(path: string): string {
  if (!path) return '';
  const normalized = path.replace(/\\/g, '/');
  const parts = normalized.split('/').filter(Boolean);
  return parts.length ? parts[parts.length - 1] : path;
}

function joinStack(values: string[], fallback = 'Unknown'): string {
  if (!values.length) return fallback;
  return values.slice(0, 4).join(', ');
}

function formatBytes(value: number | null | undefined): string {
  if (!value) return 'Unknown size';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(value: string): string {
  if (!value) return 'Not generated';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function eventTone(category: string): StatusTone {
  if (category === 'security' || category === 'climate') return 'watch';
  if (category === 'economy' || category === 'technology') return 'busy';
  if (category === 'health') return 'good';
  return 'quiet';
}

function eventPosition(event: MorningEvent): { left: string; top: string } {
  const lon = typeof event.longitude === 'number' ? event.longitude : 0;
  const lat = typeof event.latitude === 'number' ? event.latitude : 0;
  const left = Math.max(4, Math.min(96, ((lon + 180) / 360) * 100));
  const top = Math.max(8, Math.min(92, ((90 - lat) / 180) * 100));
  return { left: `${left}%`, top: `${top}%` };
}

function ContextTile({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div
      className="min-w-0 rounded-md border px-4 py-3"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
    >
      <div
        className="mb-1 flex items-center gap-2 text-xs"
        style={{ color: 'var(--color-text-tertiary)' }}
      >
        {icon}
        <span>{label}</span>
      </div>
      <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {value || 'Unavailable'}
      </div>
      {detail && (
        <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {detail}
        </div>
      )}
    </div>
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
  const [events, setEvents] = useState<MorningEvent[]>([]);
  const [worldMonitor, setWorldMonitor] = useState<WorldMonitorStatus | null>(null);
  const [syncStatus, setSyncStatus] = useState<WorldMonitorSyncStatus | null>(null);
  const [live, setLive] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchWorldEvents(24),
      fetchWorldMonitorStatus().catch(() => null),
      fetchWorldMonitorSyncStatus().catch(() => null),
    ])
      .then(([items, wmStatus, wmSync]) => {
        if (cancelled) return;
        setEvents(items);
        setWorldMonitor(wmStatus);
        setSyncStatus(wmSync);
        setLive(true);
      })
      .catch(() => {
        if (cancelled) return;
        setEvents([]);
        setLive(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const runWorldMonitorSync = async () => {
    setSyncing(true);
    try {
      const sync = await syncWorldMonitor();
      setSyncStatus(sync);
      const [items, wmStatus] = await Promise.all([
        fetchWorldEvents(24),
        fetchWorldMonitorStatus(),
      ]);
      setEvents(items);
      setWorldMonitor(wmStatus);
      setLive(true);
    } finally {
      setSyncing(false);
    }
  };

  const mapSignals = events.length
    ? events
    : worldSignals.map((signal, index) => ({
        id: `mock-${signal.city}`,
        title: signal.label,
        category: signal.tone,
        summary: signal.label,
        source_url: '',
        source_name: 'Mock fallback',
        published_at: '',
        latitude: null,
        longitude: null,
        location_name: signal.city,
        importance: 2,
        metadata: { x: signal.x, y: signal.y },
        created_at: '',
        fallbackIndex: index,
      } as MorningEvent & { fallbackIndex: number }));

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <ShellPanel title="World Map" action={live ? 'cached events' : 'mock signals'}>
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
        {mapSignals.map((event) => {
          const tone = eventTone(event.category);
          const style = toneStyle(tone);
          const fallback = worldSignals[(event as MorningEvent & { fallbackIndex?: number }).fallbackIndex ?? 0];
          const position =
            typeof event.latitude === 'number' && typeof event.longitude === 'number'
              ? eventPosition(event)
              : { left: fallback.x, top: fallback.y };
          return (
            <div
              key={event.id}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={position}
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
                <div className="font-semibold">{event.location_name || event.category}</div>
                <div className="mt-1" style={{ color: 'var(--color-text-secondary)' }}>
                  {event.title}
                </div>
              </div>
            </div>
          );
        })}
        </div>
      </ShellPanel>

      <ShellPanel title="WorldMonitor" action={worldMonitor?.connected ? 'connected' : 'optional'}>
        <div className="grid gap-3">
          <StatusPill tone={worldMonitor?.connected ? 'good' : worldMonitor?.installed ? 'watch' : 'quiet'}>
            {worldMonitor?.connected ? 'Local API' : worldMonitor?.installed ? 'Repo detected' : 'Not connected'}
          </StatusPill>
          <div className="grid gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            <span>Cache: {worldMonitor?.cached_event_count ?? 0} events</span>
            <span>Sync: {formatTime(syncStatus?.completed_at || worldMonitor?.last_sync_at || '')}</span>
            <span>Source: {worldMonitor?.base_url || worldMonitor?.local_repo_path || 'Not detected'}</span>
          </div>
          <button
            type="button"
            disabled={syncing}
            onClick={runWorldMonitorSync}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-xs font-medium disabled:opacity-50"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
              background: 'var(--color-bg-secondary)',
            }}
          >
            <RefreshCw size={14} />
            {syncing ? 'Syncing' : 'Sync local'}
          </button>
        </div>
      </ShellPanel>
    </div>
  );
}

function DailyBriefingSection() {
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [status, setStatus] = useState<BriefingStatus | null>(null);
  const [worldMonitor, setWorldMonitor] = useState<WorldMonitorStatus | null>(null);
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadBriefing = async () => {
    try {
      const [latest, currentStatus] = await Promise.all([
        fetchLatestMorningBriefing(),
        fetchBriefingStatus(),
      ]);
      setBriefing(latest);
      setStatus(currentStatus);
      setWorldMonitor(await fetchWorldMonitorStatus().catch(() => null));
      setLive(true);
    } catch {
      setBriefing(null);
      setStatus(null);
      setLive(false);
    }
  };

  useEffect(() => {
    loadBriefing();
  }, []);

  const regenerate = async () => {
    setBusy(true);
    try {
      const next = await regenerateMorningBriefing();
      setBriefing(next);
      setLive(true);
      const currentStatus = await fetchBriefingStatus();
      setStatus(currentStatus);
      setWorldMonitor(await fetchWorldMonitorStatus().catch(() => null));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Daily Briefing" action={live ? 'live cache' : 'waiting for backend'}>
        <div className="grid gap-3">
          <div className="grid grid-cols-3 gap-3">
            {[
              ['Sources', String(status?.source_count ?? briefing?.source_links.length ?? 0)],
              ['Events', String(status?.event_count ?? briefing?.events.length ?? 0)],
              ['WorldMonitor', worldMonitor?.connected ? 'Local API' : 'Optional'],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-md border p-3"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</div>
                <div className="mt-1 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>{value}</div>
              </div>
            ))}
          </div>
          <button
            type="button"
            disabled={busy || status?.privacy_mode}
            onClick={regenerate}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium disabled:opacity-50"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
              background: 'var(--color-bg-secondary)',
            }}
          >
            <RefreshCw size={15} />
            {busy ? 'Regenerating' : status?.privacy_mode ? 'Privacy cache only' : 'Regenerate'}
          </button>
        </div>
      </ShellPanel>

      <ShellPanel title={briefing?.title || 'Latest Briefing'} action={formatTime(briefing?.generated_at || '')}>
        {briefing ? (
          <div className="grid gap-4">
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {briefing.summary}
            </p>
            <div className="grid gap-2">
              {briefing.events.slice(0, 5).map((event) => (
                <div
                  key={event.id}
                  className="rounded-md border p-3"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                      {event.title}
                    </div>
                    <StatusPill tone={eventTone(event.category)}>{event.category}</StatusPill>
                  </div>
                  <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                    {event.summary}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    <span>{event.source_name || 'Source'}</span>
                    {event.metadata?.source === 'worldmonitor' && <span>WorldMonitor</span>}
                    {event.source_url && (
                      <a href={event.source_url} target="_blank" rel="noreferrer" style={{ color: 'var(--color-accent)' }}>
                        Source
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            No cached briefing yet.
          </p>
        )}
      </ShellPanel>
    </div>
  );
}

function ImportantEventsSection() {
  const [events, setEvents] = useState<MorningEvent[]>([]);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMorningEvents(40)
      .then((items) => {
        if (cancelled) return;
        setEvents(items);
        setLive(true);
      })
      .catch(() => {
        if (cancelled) return;
        setEvents([]);
        setLive(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = events.slice(0, 12);

  return (
    <ShellPanel title="Important Events" action={live ? 'cached events' : 'waiting for backend'}>
      <div className="grid gap-3 md:grid-cols-2">
        {visible.length ? (
          visible.map((event) => (
            <div
              key={event.id}
              className="rounded-md border p-4"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {event.title}
                </div>
                <StatusPill tone={eventTone(event.category)}>{event.category}</StatusPill>
              </div>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {event.summary}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                <span>{event.location_name || 'Global'}</span>
                <span>{event.source_name || 'Source'}</span>
                {event.source_url && (
                  <a href={event.source_url} target="_blank" rel="noreferrer" style={{ color: 'var(--color-accent)' }}>
                    Source
                  </a>
                )}
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            No cached events yet.
          </p>
        )}
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

function valueAsString(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return '';
}

function RepoSection() {
  const [summary, setSummary] = useState<RepoSummaryResponse | null>(null);
  const [results, setResults] = useState<RepoSemanticSearchResult[]>([]);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<'loading' | 'ready' | 'offline'>('loading');

  const loadRepo = async () => {
    setStatus('loading');
    try {
      const data = await fetchRepoSummary();
      setSummary(data);
      setStatus('ready');
    } catch {
      setSummary(null);
      setStatus('offline');
    }
  };

  useEffect(() => {
    loadRepo();
  }, []);

  const runRepoSearch = async () => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    try {
      const data = await searchRepoIndex(query, 8);
      setResults(data);
      setStatus('ready');
    } catch {
      setResults([]);
      setStatus('offline');
    }
  };

  const stack = summary?.detected_stack;
  const architecture = summary?.architecture;
  const graph = summary?.dependency_graph;
  const modules = architecture?.modules ?? [];
  const dependencies = graph?.direct_dependencies ?? [];

  return (
    <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <ShellPanel title="Detected Stack" action={status === 'ready' ? 'local index' : status}>
        <div className="grid gap-3 md:grid-cols-2">
          <ContextTile
            icon={<FolderGit2 size={15} />}
            label="Repository"
            value={basename(summary?.root || '') || 'Unavailable'}
            detail={summary?.root ? compactPath(summary.root) : undefined}
          />
          <ContextTile
            icon={<GitBranch size={15} />}
            label="Branch"
            value={summary?.current_branch || 'No branch'}
            detail={stack?.project_type || 'unknown'}
          />
          <ContextTile
            icon={<Code2 size={15} />}
            label="Languages"
            value={joinStack(stack?.languages ?? [])}
            detail={`${summary?.indexed_file_count ?? 0} searchable files`}
          />
          <ContextTile
            icon={<Package size={15} />}
            label="Build"
            value={joinStack([...(stack?.package_managers ?? []), ...(stack?.build_systems ?? [])])}
            detail={joinStack(stack?.frameworks ?? [])}
          />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {(stack?.frameworks ?? []).slice(0, 12).map((item) => (
            <StatusPill key={item} tone="quiet">{item}</StatusPill>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') runRepoSearch();
            }}
            placeholder="Search repo"
            className="min-w-0 flex-1 rounded-md border px-3 py-2 text-sm outline-none"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
              background: 'var(--color-bg-secondary)',
            }}
          />
          <button
            type="button"
            onClick={runRepoSearch}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            title="Search"
          >
            <Search size={16} />
          </button>
          <button
            type="button"
            onClick={loadRepo}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </ShellPanel>

      <ShellPanel title="Architecture Summary" action="passive">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
            <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>Entry points</div>
            <div className="mt-2 space-y-1">
              {(architecture?.entry_points ?? []).slice(0, 6).map((path) => (
                <div key={path} className="truncate font-mono text-xs" style={{ color: 'var(--color-text)' }}>{path}</div>
              ))}
              {!architecture?.entry_points?.length && <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>None detected</div>}
            </div>
          </div>
          <div className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
            <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>Build files</div>
            <div className="mt-2 space-y-1">
              {(architecture?.build_files ?? []).slice(0, 6).map((path) => (
                <div key={path} className="truncate font-mono text-xs" style={{ color: 'var(--color-text)' }}>{path}</div>
              ))}
              {!architecture?.build_files?.length && <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>None detected</div>}
            </div>
          </div>
        </div>
        <div className="mt-4 grid gap-2">
          {modules.slice(0, 8).map((module) => (
            <div key={valueAsString(module.name)} className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_80px_1.2fr]" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <span className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{valueAsString(module.name)}</span>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{valueAsString(module.file_count)} files</span>
              <span className="truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {Object.keys((module.languages as Record<string, unknown>) || {}).join(', ') || 'mixed'}
              </span>
            </div>
          ))}
        </div>
      </ShellPanel>

      <ShellPanel title="Repo Search" action={`${results.length} matches`}>
        <div className="space-y-2">
          {results.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Search results will appear here.
            </div>
          )}
          {results.map((result) => (
            <div key={result.path} className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="truncate font-mono text-sm" style={{ color: 'var(--color-text)' }}>{result.path}</span>
                <StatusPill tone="quiet">{result.score.toFixed(2)}</StatusPill>
              </div>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>{result.summary}</p>
            </div>
          ))}
        </div>
      </ShellPanel>

      <ShellPanel title="Dependency Overview" action={`${dependencies.length} direct`}>
        <div className="grid gap-2 md:grid-cols-2">
          {dependencies.slice(0, 18).map((dependency) => (
            <div key={`${dependency.ecosystem}-${dependency.name}-${dependency.source}`} className="rounded-md border px-3 py-2" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{dependency.name}</div>
              <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {dependency.ecosystem} / {basename(dependency.source)}
              </div>
            </div>
          ))}
          {dependencies.length === 0 && <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>No manifest dependencies detected.</div>}
        </div>
      </ShellPanel>
    </div>
  );
}

function CodingSection() {
  const [panel, setPanel] = useState<CodingPanelSnapshot | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'offline'>('loading');

  const loadCodingPanel = async () => {
    setStatus('loading');
    try {
      const data = await fetchCodingPanel();
      setPanel(data);
      setStatus('ready');
    } catch {
      setPanel(null);
      setStatus('offline');
    }
  };

  useEffect(() => {
    loadCodingPanel();
  }, []);

  const stack = panel?.current_stack;
  const build = panel?.build_health;
  const health = panel?.repo_health;
  const architecture = panel?.architecture_overview;
  const recentErrors = panel?.recent_errors ?? [];
  const fixes = panel?.suggested_fixes ?? [];
  const stackLabels = [
    ...(stack?.specializations ?? []),
    ...(stack?.frameworks ?? []),
    ...(stack?.build_systems ?? []),
  ];

  return (
    <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <ShellPanel title="Build Health" action={status === 'ready' ? 'local only' : status}>
        <div className="grid gap-3 md:grid-cols-3">
          <ContextTile
            icon={<Gauge size={15} />}
            label="Build"
            value={build?.status || 'Unknown'}
            detail={build?.summary || 'No build output captured'}
          />
          <ContextTile
            icon={<Activity size={15} />}
            label="Repo"
            value={health ? `${health.score}/100` : 'Unknown'}
            detail={health?.status || 'No health signal'}
          />
          <ContextTile
            icon={<LockKeyhole size={15} />}
            label="Mode"
            value={panel?.privacy_mode ? 'Privacy' : 'Local'}
            detail={panel?.cloud_uploaded ? 'Cloud upload detected' : 'No cloud upload'}
          />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {(stackLabels.length ? stackLabels : ['No stack detected']).slice(0, 12).map((item) => (
            <StatusPill key={item} tone="quiet">{item}</StatusPill>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={loadCodingPanel}
            className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
          >
            <RefreshCw size={16} />
            <span>Refresh</span>
          </button>
        </div>
      </ShellPanel>

      <ShellPanel title="Current Stack" action={stack?.project_type || 'unknown'}>
        <div className="grid gap-3 md:grid-cols-2">
          <ContextTile
            icon={<Code2 size={15} />}
            label="Languages"
            value={joinStack(stack?.languages ?? [])}
            detail={joinStack(stack?.package_managers ?? [])}
          />
          <ContextTile
            icon={<Cpu size={15} />}
            label="Runtime"
            value={stack?.java_version ? `Java ${stack.java_version}` : stack?.node_package_manager || 'Mixed'}
            detail={stack?.minecraft_version ? `Minecraft ${stack.minecraft_version}` : joinStack(stack?.build_systems ?? [])}
          />
        </div>
        <div className="mt-4 grid gap-2">
          {(health?.strengths ?? []).slice(0, 4).map((item) => (
            <div key={item} className="rounded-md border px-3 py-2 text-sm" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
              {item}
            </div>
          ))}
          {!(health?.strengths ?? []).length && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Stack signals will appear after the local index runs.
            </div>
          )}
        </div>
      </ShellPanel>

      <ShellPanel title="Recent Errors" action={`${recentErrors.length} detected`}>
        <div className="space-y-3">
          {recentErrors.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              No recent build or terminal errors are captured.
            </div>
          )}
          {recentErrors.slice(0, 5).map((error) => (
            <div key={error.category} className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{error.category}</span>
                <StatusPill tone={error.severity === 'error' ? 'watch' : 'quiet'}>{error.severity}</StatusPill>
              </div>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>{error.summary}</p>
              {!!error.evidence.length && (
                <div className="mt-2 truncate font-mono text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {error.evidence[0]}
                </div>
              )}
            </div>
          ))}
        </div>
      </ShellPanel>

      <ShellPanel title="Suggested Fixes" action="advisory">
        <div className="space-y-3">
          {fixes.slice(0, 6).map((fix) => (
            <div key={`${fix.title}-${fix.command}`} className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{fix.title}</span>
                <StatusPill tone={fix.risk === 'medium' ? 'watch' : 'quiet'}>{fix.risk}</StatusPill>
              </div>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>{fix.rationale}</p>
              {fix.command && (
                <div className="mt-2 truncate font-mono text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {fix.command}
                </div>
              )}
            </div>
          ))}
          {fixes.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Suggestions will appear when the analyzer has build output or repo health signals.
            </div>
          )}
        </div>
      </ShellPanel>

      <ShellPanel title="Architecture Overview" action="repo aware">
        <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          {architecture?.summary || 'Architecture explanation will appear after repo indexing completes.'}
        </p>
        <div className="mt-4 grid gap-2">
          {(architecture?.major_systems ?? []).slice(0, 6).map((system) => (
            <div key={valueAsString(system.name)} className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_80px_1.2fr]" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <span className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{valueAsString(system.name)}</span>
              <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{valueAsString(system.file_count)} files</span>
              <span className="truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {Object.keys((system.languages as Record<string, unknown>) || {}).join(', ') || 'mixed'}
              </span>
            </div>
          ))}
        </div>
      </ShellPanel>

      <ShellPanel title="Risky Refactors" action="passive">
        <div className="space-y-2">
          {(architecture?.risky_refactors ?? health?.concerns ?? []).slice(0, 8).map((item) => (
            <div key={item} className="rounded-md border px-3 py-2 text-sm" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
              {item}
            </div>
          ))}
          {!(architecture?.risky_refactors ?? health?.concerns ?? []).length && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              No refactor risks detected yet.
            </div>
          )}
        </div>
      </ShellPanel>
    </div>
  );
}

function TerminalSection() {
  const [context, setContext] = useState<TerminalContextSnapshot | null>(null);
  const [live, setLive] = useState(false);
  const [queuedId, setQueuedId] = useState<string | null>(null);

  const loadTerminalContext = async () => {
    try {
      const data = await fetchTerminalContext();
      setContext(data);
      setLive(true);
    } catch {
      setContext(null);
      setLive(false);
    }
  };

  useEffect(() => {
    loadTerminalContext();
  }, []);

  const queueApproval = async (commandId: string) => {
    setQueuedId(commandId);
    try {
      await requestTerminalCommandApproval(commandId);
      await loadTerminalContext();
    } finally {
      setQueuedId(null);
    }
  };

  const current = context?.current;
  const analysis = context?.error_summary;
  const history = context?.history ?? [];
  const suggestions = analysis?.suggested_commands ?? [];

  return (
    <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <ShellPanel title="Terminal Co-Pilot" action={live ? 'passive live' : 'waiting'}>
        <div className="grid gap-3 md:grid-cols-3">
          <ContextTile
            icon={<TerminalSquare size={15} />}
            label="Shell"
            value={context?.shell_type || current?.shell_type || 'Unknown'}
            detail={context?.privacy_mode ? 'Privacy Mode' : 'Local only'}
          />
          <ContextTile
            icon={<FolderGit2 size={15} />}
            label="Project"
            value={basename(String(context?.project_context?.git_repository || context?.cwd || ''))}
            detail={compactPath(context?.cwd || current?.cwd || '')}
          />
          <ContextTile
            icon={<Code2 size={15} />}
            label="Last exit"
            value={current?.exit_code === undefined || current?.exit_code === null ? 'None' : String(current.exit_code)}
            detail={current?.timestamp ? new Date(current.timestamp).toLocaleString() : 'No capture yet'}
          />
        </div>

        <div
          className="mt-4 rounded-md border p-4 font-mono text-sm"
          style={{
            borderColor: 'var(--color-border)',
            background: 'var(--color-code-bg)',
            color: 'var(--color-text)',
          }}
        >
          <div style={{ color: 'var(--color-text-tertiary)' }}>
            $ {current?.command || 'No terminal command captured'}
          </div>
          {current?.output_preview && (
            <pre className="mt-3 max-h-44 overflow-auto whitespace-pre-wrap text-xs leading-5">
              {current.output_preview}
            </pre>
          )}
        </div>

        <div className="mt-4 grid gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              {analysis?.has_error ? <AlertTriangle size={16} style={{ color: 'var(--color-warning)' }} /> : <ShieldCheck size={16} style={{ color: 'var(--color-success)' }} />}
              <span>Last Error</span>
            </div>
            <StatusPill tone={analysis?.has_error ? 'watch' : 'good'}>
              {analysis?.has_error ? 'Needs attention' : 'Clear'}
            </StatusPill>
          </div>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            {analysis?.summary || 'Terminal context will appear after a local shell integration records a completed command.'}
          </p>
          {!!analysis?.patterns.length && (
            <div className="flex flex-wrap gap-2">
              {analysis.patterns.map((pattern) => (
                <StatusPill key={pattern} tone="quiet">{pattern}</StatusPill>
              ))}
            </div>
          )}
        </div>
      </ShellPanel>

      <div className="grid gap-4">
        <ShellPanel title="Suggested Fixes" action="dry run">
          <div className="space-y-3">
            {(analysis?.possible_fixes.length ? analysis.possible_fixes : ['No fixes suggested yet.']).map((fix) => (
              <div
                key={fix}
                className="rounded-md border px-3 py-3 text-sm"
                style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
              >
                {fix}
              </div>
            ))}
          </div>
        </ShellPanel>

        <ShellPanel title="Suggested Commands" action="approval gated">
          <div className="space-y-3">
            {suggestions.length === 0 && (
              <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                Safe next commands will appear after a captured error.
              </div>
            )}
            {suggestions.map((command) => (
              <div
                key={command.id}
                className="rounded-md border p-3"
                style={{
                  borderColor: command.dangerous ? 'var(--color-warning)' : 'var(--color-border)',
                  background: 'var(--color-bg-secondary)',
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-mono text-sm" style={{ color: 'var(--color-text)' }}>
                      {command.command}
                    </div>
                    <p className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      {command.reason}
                    </p>
                  </div>
                  <StatusPill tone={command.dangerous ? 'watch' : 'quiet'}>
                    {command.dangerous ? 'Dangerous' : command.permission_level}
                  </StatusPill>
                </div>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    Dry run: {String(command.dry_run_preview?.would_action || command.permission_action)}
                  </span>
                  {command.requires_approval && (
                    <button
                      type="button"
                      onClick={() => queueApproval(command.id)}
                      disabled={queuedId === command.id}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border disabled:opacity-60"
                      style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
                      title="Request approval"
                    >
                      <ShieldAlert size={15} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </ShellPanel>
      </div>

      <ShellPanel title="Recent Commands" action={`${history.length} shown`}>
        <div className="space-y-2">
          {history.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              No terminal history has been captured.
            </div>
          )}
          {history.map((item) => (
            <div
              key={`${item.timestamp}-${item.command}`}
              className="grid gap-2 rounded-md border px-3 py-3 md:grid-cols-[1fr_80px_140px]"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <span className="truncate font-mono text-sm" style={{ color: 'var(--color-text)' }}>
                {item.command}
              </span>
              <StatusPill tone={item.exit_code ? 'watch' : 'good'}>
                {item.exit_code === null ? 'n/a' : item.exit_code}
              </StatusPill>
              <span className="truncate text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {compactPath(item.cwd)}
              </span>
            </div>
          ))}
        </div>
      </ShellPanel>
    </div>
  );
}

function VoiceSection() {
  const [status, setStatus] = useState<VoicePttStatus | null>(null);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<'idle' | 'starting' | 'stopping' | 'transcribing'>('idle');

  const loadVoiceStatus = async () => {
    try {
      const data = await fetchVoicePttStatus();
      setStatus(data);
      setError('');
    } catch {
      setStatus(null);
    }
  };

  useEffect(() => {
    loadVoiceStatus();
  }, []);

  const startHold = async () => {
    if (busy !== 'idle' || status?.recording) return;
    setBusy('starting');
    setTranscript('');
    setError('');
    try {
      const response = await startVoicePttRecording(status?.active_agent_id || '');
      setStatus(response.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Voice start failed');
    } finally {
      setBusy('idle');
    }
  };

  const stopHold = async () => {
    if (busy !== 'idle' || !status?.recording) return;
    setBusy('stopping');
    setError('');
    try {
      const response = await stopVoicePttRecording();
      setStatus(response.status);
      setBusy('transcribing');
      const result = await transcribeLatestVoiceRecording();
      setTranscript(result.text);
      await loadVoiceStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Voice stop failed');
    } finally {
      setBusy('idle');
    }
  };

  const recording = status?.recording ?? false;
  const latest = status?.latest;
  const intent = latest?.intent_preview;
  const buttonBusy = busy !== 'idle';
  const buttonLabel = recording ? 'Release to stop' : buttonBusy ? 'Working' : 'Hold to talk';
  const stateLabel = recording ? 'Recording' : busy === 'transcribing' ? 'Transcribing' : 'Idle';

  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Voice Push-to-Talk" action="manual">
        <div className="grid gap-3 md:grid-cols-3">
          <ContextTile
            icon={<Mic2 size={15} />}
            label="State"
            value={stateLabel}
            detail={status?.requires_explicit_approval ? 'Approval required' : 'Approved in settings'}
          />
          <ContextTile
            icon={<ShieldCheck size={15} />}
            label="Privacy"
            value={status?.privacy_mode ? 'Privacy Mode' : 'Local'}
            detail={latest?.persisted_raw_audio ? 'Raw audio kept' : 'Metadata only'}
          />
          <ContextTile
            icon={<Brain size={15} />}
            label="Agent"
            value={latest?.active_agent || status?.active_agent_id || 'Workspace'}
            detail={latest?.active_mode || status?.active_mode_id || 'mode pending'}
          />
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onPointerDown={(event) => {
              event.preventDefault();
              startHold();
            }}
            onPointerUp={(event) => {
              event.preventDefault();
              stopHold();
            }}
            onPointerLeave={() => {
              if (recording) stopHold();
            }}
            disabled={buttonBusy}
            className="inline-flex h-12 min-w-40 items-center justify-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors disabled:opacity-60"
            style={{
              borderColor: recording ? 'var(--color-error)' : 'var(--color-border)',
              color: recording ? 'white' : 'var(--color-text)',
              background: recording ? 'var(--color-error)' : 'var(--color-bg-secondary)',
            }}
            title="Hold to talk"
          >
            {recording ? <Square size={16} /> : <Mic2 size={17} />}
            {buttonLabel}
          </button>
          <button
            type="button"
            onClick={loadVoiceStatus}
            className="flex h-12 w-12 items-center justify-center rounded-md border transition-colors"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
              background: 'var(--color-bg-secondary)',
            }}
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          <StatusPill tone={recording ? 'busy' : status?.privacy_mode ? 'watch' : 'quiet'}>
          {recording ? 'Live capture' : status?.privacy_mode ? 'Privacy gate' : 'Ready'}
          </StatusPill>
          <StatusPill tone={status?.transcription_available ? 'good' : 'watch'}>
            {status?.transcription_available ? 'Local STT' : 'STT unavailable'}
          </StatusPill>
        </div>

        {error && (
          <p className="mt-4 text-sm" style={{ color: 'var(--color-error)' }}>
            {error}
          </p>
        )}
      </ShellPanel>

      <ShellPanel title="Transcript Preview" action="not sent">
        <div
          className="min-h-40 rounded-md border p-4 text-sm leading-6"
          style={{
            borderColor: 'var(--color-border)',
            background: 'var(--color-bg-secondary)',
            color: transcript || latest?.transcript ? 'var(--color-text)' : 'var(--color-text-tertiary)',
          }}
        >
          {transcript || latest?.transcript || 'No transcript yet'}
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <ContextTile
            icon={<Clock3 size={15} />}
            label="Duration"
            value={latest?.duration_seconds ? `${latest.duration_seconds.toFixed(1)}s` : '0.0s'}
            detail={latest?.stopped_at ? new Date(latest.stopped_at * 1000).toLocaleString() : 'No stop event'}
          />
          <ContextTile
            icon={<Package size={15} />}
            label="Bytes"
            value={formatBytes(latest?.byte_size)}
            detail={latest?.raw_audio_available ? 'Temporary audio' : 'No raw audio'}
          />
          <ContextTile
            icon={<Activity size={15} />}
            label="Backend"
            value={latest?.backend || 'Local pending'}
            detail="No agent dispatch"
          />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <ContextTile
            icon={<Search size={15} />}
            label="Intent"
            value={intent?.interpreted_intent || 'Pending'}
            detail={intent?.planned_actions?.[0] || 'Preview only'}
          />
          <ContextTile
            icon={<ShieldAlert size={15} />}
            label="Risk"
            value={intent?.risk_level || 'Unknown'}
            detail={intent?.approval_required ? 'Approval required' : 'No execution'}
          />
          <ContextTile
            icon={<LockKeyhole size={15} />}
            label="Local"
            value="Local only"
            detail="No wake word"
          />
        </div>
      </ShellPanel>
    </div>
  );
}

function VisionSection() {
  const [visualContext, setVisualContext] = useState<VisualContext | null>(null);
  const [screenshots, setScreenshots] = useState<ScreenshotMetadata[]>([]);
  const [status, setStatus] = useState<'ready' | 'loading' | 'offline'>('loading');
  const [capturing, setCapturing] = useState(false);
  const [notice, setNotice] = useState('');

  const loadVisionContext = async () => {
    setStatus('loading');
    try {
      const [latest, recent] = await Promise.all([
        fetchLatestVisualContext(),
        fetchRecentVisionScreenshots(8),
      ]);
      setVisualContext(latest);
      setScreenshots(recent);
      setStatus('ready');
      setNotice('');
    } catch {
      setStatus('offline');
    }
  };

  useEffect(() => {
    loadVisionContext();
  }, []);

  const capture = async () => {
    setCapturing(true);
    setNotice('');
    try {
      await captureVisionScreenshot();
      await loadVisionContext();
    } catch {
      setNotice('Capture blocked or unavailable. Privacy Mode queues approval before screenshots.');
      setStatus('offline');
    } finally {
      setCapturing(false);
    }
  };

  const latest = visualContext?.latest_screenshot ?? null;
  const dimensions = latest?.width && latest?.height ? `${latest.width} x ${latest.height}` : 'Unknown';

  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Vision Context" action="passive only">
        <div className="grid gap-3 md:grid-cols-2">
          <ContextTile
            icon={<Eye size={15} />}
            label="Latest App"
            value={latest?.active_application || 'No screenshot'}
            detail={latest?.active_window_title || (latest?.redacted ? 'Redacted locally' : undefined)}
          />
          <ContextTile
            icon={<Image size={15} />}
            label="Latest Frame"
            value={dimensions}
            detail={latest?.captured_at ? new Date(latest.captured_at).toLocaleString() : 'No capture yet'}
          />
          <ContextTile
            icon={<ShieldCheck size={15} />}
            label="Storage"
            value={visualContext?.cloud_uploaded ? 'Cloud' : 'Local only'}
            detail={latest?.file_path ? compactPath(latest.file_path) : 'No image bytes exposed here'}
          />
          <ContextTile
            icon={<Camera size={15} />}
            label="Screenshots"
            value={String(visualContext?.screenshot_count ?? 0)}
            detail={visualContext?.privacy_mode ? 'Privacy Mode redaction' : 'Explicit capture only'}
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={capture}
            disabled={capturing}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-60"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
              background: 'var(--color-bg-secondary)',
            }}
            title="Capture screenshot"
          >
            <Camera size={16} />
            {capturing ? 'Capturing' : 'Capture'}
          </button>
          <button
            type="button"
            onClick={loadVisionContext}
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
          <StatusPill tone={status === 'ready' ? 'good' : status === 'loading' ? 'busy' : 'watch'}>
            {status}
          </StatusPill>
        </div>

        {notice && (
          <p className="mt-4 rounded-md border px-3 py-2 text-sm" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
            {notice}
          </p>
        )}
      </ShellPanel>

      <ShellPanel title="Recent Screenshots" action={`${screenshots.length} shown`}>
        <div className="space-y-2">
          {screenshots.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              No screenshots have been explicitly captured.
            </div>
          )}
          {screenshots.map((screenshot) => {
            const size = screenshot.width && screenshot.height ? `${screenshot.width} x ${screenshot.height}` : 'Unknown';
            return (
              <div
                key={screenshot.id}
                className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_120px_110px]"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                    {screenshot.active_application || 'Unknown app'}
                  </div>
                  <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    {screenshot.redacted ? 'Redacted locally' : compactPath(screenshot.file_path)}
                  </div>
                </div>
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {size}
                </span>
                <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {formatBytes(screenshot.byte_size)}
                </span>
              </div>
            );
          })}
        </div>
      </ShellPanel>
    </div>
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
  const [startup, setStartup] = useState<StartupStatus | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'offline'>('loading');
  const [acting, setActing] = useState<'startup' | 'briefing' | ''>('');

  const refreshStartup = async () => {
    setStatus('loading');
    try {
      setStartup(await fetchStartupStatus());
      setStatus('ready');
    } catch {
      setStartup(null);
      setStatus('offline');
    }
  };

  useEffect(() => {
    refreshStartup();
  }, []);

  const toggleStartup = async () => {
    setActing('startup');
    try {
      const next = startup?.launch_at_login ? await removeStartup() : await installStartup();
      setStartup(next);
      setStatus('ready');
    } catch {
      setStatus('offline');
    } finally {
      setActing('');
    }
  };

  const triggerBriefing = async () => {
    setActing('briefing');
    try {
      const result = await triggerStartupMorningBriefing(true);
      const next = await fetchStartupStatus();
      if (result.briefing) {
        next.scheduler.last_morning_briefing_at = result.last_morning_briefing_at;
        next.scheduler.last_morning_briefing_date = result.briefing.briefing_date;
      }
      setStartup(next);
      setStatus('ready');
    } catch {
      setStatus('offline');
    } finally {
      setActing('');
    }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <ShellPanel title="Startup">
        <div className="grid gap-3">
          <div className="grid gap-3 md:grid-cols-2">
            {[
              ['Launch at login', startup?.launch_at_login ? 'Enabled' : 'Disabled'],
              ['Startup status', startup?.launch_agent.valid ? 'Installed' : startup?.launch_agent.installed ? 'Needs repair' : 'Not installed'],
              ['Scheduler', startup?.scheduler.enabled ? 'Passive' : 'Paused'],
              ['Last briefing', formatTime(startup?.scheduler.last_morning_briefing_at || '')],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-md border p-4"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {label}
                </div>
                <div className="mt-2 truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={acting === 'startup'}
              onClick={toggleStartup}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium disabled:opacity-50"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
                background: startup?.launch_at_login ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
              }}
            >
              {startup?.launch_at_login ? <CheckCircle2 size={15} /> : <Circle size={15} />}
              {acting === 'startup' ? 'Updating' : 'Launch at login'}
            </button>
            <button
              type="button"
              disabled={acting === 'briefing' || startup?.privacy_mode}
              onClick={triggerBriefing}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium disabled:opacity-50"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
                background: 'var(--color-bg-secondary)',
              }}
            >
              <RefreshCw size={15} />
              {acting === 'briefing' ? 'Generating' : startup?.privacy_mode ? 'Privacy cache only' : 'Trigger briefing'}
            </button>
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
            {status === 'offline'
              ? 'Startup API unavailable'
              : startup?.launch_agent.error || 'Local scheduling only; no startup telemetry'}
          </div>
        </div>
      </ShellPanel>

      <ShellPanel title="Runtime">
        <div className="grid gap-3">
          {[
            ['Model routing', 'Balanced'],
            ['Notifications', 'Manual only'],
            ['Workspace mode', startup?.privacy_mode ? 'Privacy' : 'Local'],
            ['Background loop', startup?.scheduler.background_loop ? 'Active' : 'Off'],
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
    </div>
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
  if (section === 'daily-briefing') return <DailyBriefingSection />;
  if (section === 'important-events') return <ImportantEventsSection />;
  if (section === 'tasks') return <TasksSection />;
  if (section === 'agents') return <AgentsSection />;
  if (section === 'memory') return <MemorySection />;
  if (section === 'projects') return <ProjectsSection />;
  if (section === 'coding') return <CodingSection />;
  if (section === 'repo') return <RepoSection />;
  if (section === 'voice') return <VoiceSection />;
  if (section === 'vision') return <VisionSection />;
  if (section === 'terminal') return <TerminalSection />;
  if (section === 'research') return <ResearchSection />;
  if (section === 'settings') return <SettingsSection />;
  if (section === 'permissions') return <PermissionsSection />;
  return <HomeSection />;
}

const fallbackModes: SiriModeConfig[] = [
  {
    id: 'focus',
    display_name: 'Focus',
    description: 'Keeps Siri direct, calm, and task-centered.',
    verbosity_level: 'concise',
    proactive_level: 'low',
    interruption_policy: 'priority_only',
    preferred_agents: ['coding', 'engineering'],
    memory_behavior: {},
    privacy_network_policy: { outbound_network: 'allowed' },
    voice_capture_behavior: {},
    default_model_overrides: {},
    ui_theme_metadata: { accent: 'blue' },
    notification_behavior: {},
  },
  {
    id: 'privacy',
    display_name: 'Privacy',
    description: 'Locks Siri to local-first behavior.',
    verbosity_level: 'balanced',
    proactive_level: 'off',
    interruption_policy: 'priority_only',
    preferred_agents: ['privacy', 'engineering'],
    memory_behavior: {},
    privacy_network_policy: { outbound_network: 'localhost_only', cloud_apis: 'disabled' },
    voice_capture_behavior: { activation: 'push_to_talk_only', requires_explicit_approval: true },
    default_model_overrides: { engine: 'ollama' },
    ui_theme_metadata: { accent: 'emerald' },
    notification_behavior: {},
  },
];

function ModeSwitcher({
  onModeChange,
}: {
  onModeChange: (mode: SiriModeConfig | null, live: boolean) => void;
}) {
  const [modes, setModes] = useState<SiriModeConfig[]>(fallbackModes);
  const [activeModeId, setActiveModeId] = useState('focus');
  const [live, setLive] = useState(false);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listSiriModes()
      .then((data) => {
        if (cancelled) return;
        const active = data.modes.find((mode) => mode.id === data.active_mode_id) ?? null;
        setModes(data.modes);
        setActiveModeId(data.active_mode_id);
        setLive(true);
        onModeChange(active, true);
      })
      .catch(() => {
        if (cancelled) return;
        const active = fallbackModes.find((mode) => mode.id === activeModeId) ?? fallbackModes[0];
        setModes(fallbackModes);
        setLive(false);
        onModeChange(active, false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedMode = modes.find((mode) => mode.id === activeModeId) ?? modes[0];

  const changeMode = async (modeId: string) => {
    setActiveModeId(modeId);
    const optimistic = modes.find((mode) => mode.id === modeId) ?? null;
    onModeChange(optimistic, live);
    if (!live) return;
    setSwitching(true);
    try {
      const state = await switchActiveSiriMode(modeId);
      setActiveModeId(state.active_mode_id);
      onModeChange(state.mode, true);
    } finally {
      setSwitching(false);
    }
  };

  return (
    <div
      className="rounded-md border px-4 py-3"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
    >
      <label
        htmlFor="mission-mode-select"
        className="mb-2 flex items-center gap-2 text-xs"
        style={{ color: 'var(--color-text-tertiary)' }}
      >
        <Brain size={14} />
        Mode
      </label>
      <select
        id="mission-mode-select"
        value={activeModeId}
        disabled={switching}
        onChange={(event) => changeMode(event.target.value)}
        className="h-9 w-full rounded-md border px-2 text-sm font-semibold outline-none"
        style={{
          borderColor: 'var(--color-border)',
          color: 'var(--color-text)',
          background: 'var(--color-bg)',
        }}
      >
        {modes.map((mode) => (
          <option key={mode.id} value={mode.id}>
            {mode.display_name}
          </option>
        ))}
      </select>
      <div className="mt-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {selectedMode?.verbosity_level ?? 'balanced'} / {selectedMode?.proactive_level ?? 'low'}
      </div>
      <div className="mt-1 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
        {live ? 'Live mode registry' : 'Mode fallback'}
      </div>
    </div>
  );
}

export function MissionControlPage() {
  const [activeSection, setActiveSection] = useState<MissionSectionId>('home');
  const [activeMode, setActiveMode] = useState<SiriModeConfig | null>(null);
  const [modeLive, setModeLive] = useState(false);
  const [localContext, setLocalContext] = useState<LocalContextSnapshot | null>(null);
  const [contextLive, setContextLive] = useState(false);
  const activeLabel = useMemo(
    () => missionSections.find((section) => section.id === activeSection)?.label ?? 'Home',
    [activeSection],
  );
  const refreshContext = async () => {
    try {
      const snapshot = await fetchLocalContextSnapshot();
      setLocalContext(snapshot);
      setContextLive(true);
    } catch {
      setContextLive(false);
    }
  };

  useEffect(() => {
    refreshContext();
  }, []);

  const contextTiles = useMemo(() => {
    const desktop = localContext?.desktop;
    const project = localContext?.project;
    const repo = localContext?.repo;
    const repoRoot = project?.git_repository || repo?.root || '';
    const projectName = basename(repoRoot || project?.cwd || '');
    const techStack = joinStack([
      ...(project?.languages ?? []),
      ...(project?.framework_build_system ?? []),
      ...(project?.package_manager ?? []),
    ]);
    return [
      {
        label: 'Current App',
        value: desktop?.active_application || 'Unavailable',
        detail: desktop?.active_window_title || undefined,
        icon: <AppWindow size={14} />,
      },
      {
        label: 'Current Project',
        value: projectName || 'Unavailable',
        detail: project?.project_type,
        icon: <Code2 size={14} />,
      },
      {
        label: 'Current Repo',
        value: basename(repoRoot) || 'No repo',
        detail: repoRoot ? compactPath(repoRoot) : undefined,
        icon: <FolderGit2 size={14} />,
      },
      {
        label: 'Current Branch',
        value: project?.current_branch || 'No branch',
        icon: <GitBranch size={14} />,
      },
      {
        label: 'Tech Stack',
        value: techStack,
        detail: repo?.summary?.file_count ? `${repo.summary.file_count} indexed files` : undefined,
        icon: <Package size={14} />,
      },
      {
        label: 'Clipboard Preview',
        value: desktop?.clipboard_preview || 'Empty or unavailable',
        detail: desktop?.clipboard_sensitive ? 'Redacted locally' : 'Local preview only',
        icon: <Clipboard size={14} />,
      },
    ];
  }, [localContext]);

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
            <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <ModeSwitcher
                onModeChange={(mode, liveRegistry) => {
                  setActiveMode(mode);
                  setModeLive(liveRegistry);
                }}
              />
              <ContextTile
                icon={<Activity size={14} />}
                label="Current Section"
                value={activeLabel}
                detail={
                  activeMode?.privacy_network_policy?.outbound_network === 'localhost_only'
                    ? 'Localhost network'
                    : 'Normal network'
                }
              />
              {contextTiles.map((tile) => (
                <ContextTile
                  key={tile.label}
                  icon={tile.icon}
                  label={tile.label}
                  value={tile.value}
                  detail={tile.detail}
                />
              ))}
              <button
                type="button"
                onClick={refreshContext}
                className="flex min-h-[76px] items-center justify-center gap-2 rounded-md border px-4 py-3 text-sm font-semibold transition-colors"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text)',
                  background: contextLive ? 'var(--color-bg-secondary)' : 'var(--color-accent-subtle)',
                }}
                title="Refresh local context"
              >
                <RefreshCw size={16} />
                {contextLive ? 'Refresh Context' : 'Retry Context'}
              </button>
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
            {modeLive ? `Mode: ${activeMode?.display_name ?? 'Focus'}` : 'Mode fallback'}
          </span>
        </footer>
      </div>
    </div>
  );
}
