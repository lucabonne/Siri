import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Ban,
  BookMarked,
  Brain,
  CheckCircle2,
  Circle,
  Clock3,
  Cpu,
  Eye,
  FileDown,
  FolderGit2,
  LockKeyhole,
  Pin,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react';
import {
  createMemory,
  captureVisionScreenshot,
  decideSecurityApproval,
  deleteMemory,
  disableHotkey,
  enableHotkey,
  fetchCodingPanel,
  fetchBriefingStatus,
  fetchDesktopStatus,
  fetchEngineeringProjectSummary,
  fetchEngineeringStatus,
  fetchHotkeyStatus,
  fetchLatestVisualContext,
  fetchLocalContextSnapshot,
  fetchLatestMorningBriefing,
  fetchMorningEvents,
  fetchPermissionAudit,
  fetchRepoSummary,
  fetchReleaseMissionControl,
  fetchRecentVisionScreenshots,
  fetchResearchCitations,
  fetchResearchMemoryEntries,
  fetchResearchReport,
  fetchResearchStatus,
  fetchStartupStatus,
  fetchSecurityApprovals,
  fetchTerminalContext,
  fetchTTSStatus,
  fetchTTSVoices,
  fetchVoicePttStatus,
  fetchWorldEvents,
  fetchWorldMonitorStatus,
  fetchWorldMonitorSyncStatus,
  fetchWorkflowPanel,
  listWorkspaceAgents,
  listSiriModes,
  listMemories,
  listResearch,
  openEngineeringProject,
  installStartup,
  regenerateMorningBriefing,
  removeStartup,
  requestTerminalCommandApproval,
  runReleaseRecoveryAction,
  searchRepoIndex,
  searchMemory,
  setMemoryPinned,
  startResearch,
  runWorkflow,
  startVoicePttRecording,
  speakTTS,
  switchActiveWorkspaceAgent,
  switchActiveSiriMode,
  triggerStartupMorningBriefing,
  stopVoicePttRecording,
  stopTTS,
  syncWorldMonitor,
  testHotkeyTrigger,
  transcribeLatestVoiceRecording,
  fetchPersonalizationStatus,
  listProfiles,
  switchActiveProfile,
  createProfile,
  fetchAutonomyApprovals,
  resolveAutonomyApproval,
  createAutonomyGoal,
  generateAutonomyPlan,
  startAutonomyPlan,
  pauseAutonomyPlan,
  resumeAutonomyPlan,
  stopAutonomyPlan,
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
  TTSStatus,
  TTSVoice,
  VisualContext,
  VoicePttStatus,
  WorkspaceAgentConfig,
  CodingPanelSnapshot,
  BriefingStatus,
  DailyBriefing,
  DesktopStatus,
  EngineeringProjectSummary,
  EngineeringStatus,
  HotkeyStatus,
  MorningEvent,
  ResearchReport,
  ResearchSession,
  ResearchSource,
  ReleaseMissionControlSnapshot,
  ReleaseRecoveryResult,
  StartupStatus,
  WorldMonitorStatus,
  WorldMonitorSyncStatus,
  WorkflowDefinition,
  WorkflowPanelSnapshot,
  WorkflowRun,
  Profile,
  ProfileStatus,
  Preferences,
  AutonomyApprovalRequest,
  AutonomyGoal,
  AutonomyPlan,
  AutonomyPlanStep,
  AutonomyExecutionState,
} from '../../lib/api';
import type {
  KnowledgeNote,
  KnowledgeNoteListItem,
  VaultTag,
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
  researchItems,
  settingsItems,
  terminalSignals,
  worldSignals,
} from './mockData';
import type {
  ApprovalRecord,
  MissionMemory,
  MissionSectionId,
  PermissionEvent,
  StatusTone,
} from './types';
import { LearningPanel } from '../LearningPanel';

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

function workflowTone(status: string): StatusTone {
  if (status === 'completed') return 'good';
  if (status === 'waiting_approval' || status === 'running') return 'busy';
  if (status === 'blocked' || status === 'failed') return 'watch';
  return 'quiet';
}

function WorkflowCard({
  workflow,
  running,
  onRun,
}: {
  workflow: WorkflowDefinition;
  running: boolean;
  onRun: (workflowId: string) => void;
}) {
  return (
    <div
      className="rounded-md border p-4"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Workflow size={16} style={{ color: 'var(--color-accent)' }} />
            <h3 className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              {workflow.name}
            </h3>
          </div>
          <p className="mt-2 line-clamp-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            {workflow.description}
          </p>
        </div>
        <button
          type="button"
          disabled={running}
          onClick={() => onRun(workflow.id)}
          className="inline-flex h-9 shrink-0 items-center justify-center rounded-md border px-3 text-xs font-semibold disabled:opacity-50"
          style={{
            borderColor: 'var(--color-border)',
            color: 'var(--color-text)',
            background: 'var(--color-bg)',
          }}
          title={`Run ${workflow.name}`}
        >
          <Play size={14} />
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <StatusPill tone={workflow.requires_approval ? 'watch' : 'good'}>
          {workflow.requires_approval ? 'Approval gated' : 'Local safe'}
        </StatusPill>
        <StatusPill tone="quiet">{workflow.steps.length} steps</StatusPill>
        <StatusPill tone="quiet">{workflow.allowed_agents.slice(0, 2).join(', ')}</StatusPill>
      </div>
    </div>
  );
}

function WorkflowRunRow({ run }: { run: WorkflowRun }) {
  return (
    <div
      className="grid gap-3 rounded-md border p-3 md:grid-cols-[1fr_auto]"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            {run.workflow_name}
          </span>
          <StatusPill tone={workflowTone(run.status)}>{run.status}</StatusPill>
        </div>
        <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {run.mode_id || 'mode'} / {run.agent_id || 'agent'} / {formatTime(run.updated_at)}
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
        <History size={14} />
        {run.steps.length} steps
      </div>
    </div>
  );
}

function WorkflowsSection() {
  const [snapshot, setSnapshot] = useState<WorkflowPanelSnapshot | null>(null);
  const [live, setLive] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);

  const loadWorkflows = async () => {
    try {
      const data = await fetchWorkflowPanel();
      setSnapshot(data);
      setLive(true);
    } catch {
      setSnapshot(null);
      setLive(false);
    }
  };

  useEffect(() => {
    loadWorkflows();
  }, []);

  const launch = async (workflowId: string) => {
    setRunningId(workflowId);
    try {
      await runWorkflow(workflowId, { requested_by: 'mission_control' });
      await loadWorkflows();
    } finally {
      setRunningId(null);
    }
  };

  const workflows = snapshot?.available_workflows ?? [];
  const running = snapshot?.running_workflows ?? [];
  const history = snapshot?.history ?? [];
  const approvals = snapshot?.approvals ?? [];
  const failures = snapshot?.failures ?? [];

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
      <ShellPanel title="Available Workflows" action={live ? 'local registry' : 'waiting'}>
        <div className="grid gap-3 md:grid-cols-2">
          {workflows.map((workflow) => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              running={runningId === workflow.id}
              onRun={launch}
            />
          ))}
          {!workflows.length && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Workflow registry is not available yet.
            </div>
          )}
        </div>
      </ShellPanel>

      <div className="grid gap-4">
        <ShellPanel title="Running" action={`${running.length} active`}>
          <div className="space-y-2">
            {running.map((run) => <WorkflowRunRow key={run.id} run={run} />)}
            {!running.length && (
              <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                No workflows are currently active.
              </div>
            )}
          </div>
        </ShellPanel>

        <ShellPanel title="Approvals" action={`${approvals.length} pending`}>
          <div className="space-y-2">
            {approvals.slice(0, 5).map((approval) => (
              <div key={approval.id} className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
                <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                  {approval.tool}
                </div>
                <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {approval.reason}
                </div>
              </div>
            ))}
            {!approvals.length && (
              <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                No workflow approvals are pending.
              </div>
            )}
          </div>
        </ShellPanel>

        <ShellPanel title="Failures" action={`${failures.length} recent`}>
          <div className="space-y-2">
            {failures.map((run) => <WorkflowRunRow key={run.id} run={run} />)}
            {!failures.length && (
              <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                No recent workflow failures.
              </div>
            )}
          </div>
        </ShellPanel>
      </div>

      <ShellPanel title="History" action="recent">
        <div className="grid gap-2">
          {history.slice(0, 10).map((run) => <WorkflowRunRow key={run.id} run={run} />)}
          {!history.length && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Workflow history will appear after the first run.
            </div>
          )}
        </div>
      </ShellPanel>
    </div>
  );
}

function VoiceSection() {
  const [status, setStatus] = useState<VoicePttStatus | null>(null);
  const [hotkeyStatus, setHotkeyStatus] = useState<HotkeyStatus | null>(null);
  const [ttsStatus, setTtsStatus] = useState<TTSStatus | null>(null);
  const [ttsVoices, setTtsVoices] = useState<TTSVoice[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState('');
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState('');
  const [ttsError, setTtsError] = useState('');
  const [busy, setBusy] = useState<'idle' | 'starting' | 'stopping' | 'transcribing'>('idle');
  const [hotkeyBusy, setHotkeyBusy] = useState<'idle' | 'toggle' | 'test'>('idle');
  const [ttsBusy, setTtsBusy] = useState<'idle' | 'speaking' | 'stopping'>('idle');

  const loadVoiceStatus = async () => {
    try {
      const data = await fetchVoicePttStatus();
      setStatus(data);
      setError('');
    } catch {
      setStatus(null);
    }
  };

  const loadHotkeyStatus = async () => {
    try {
      const data = await fetchHotkeyStatus();
      setHotkeyStatus(data);
    } catch {
      setHotkeyStatus(null);
    }
  };

  const loadTtsStatus = async () => {
    try {
      const [nextStatus, voices] = await Promise.all([
        fetchTTSStatus(),
        fetchTTSVoices(),
      ]);
      setTtsStatus(nextStatus);
      setTtsVoices(voices.voices);
      setSelectedVoiceId((current) => current || nextStatus.selected_voice_id || voices.voices[0]?.id || '');
      setTtsError('');
    } catch {
      setTtsStatus(null);
      setTtsVoices([]);
    }
  };

  useEffect(() => {
    loadVoiceStatus();
    loadHotkeyStatus();
    loadTtsStatus();
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

  const toggleHotkey = async () => {
    if (hotkeyBusy !== 'idle') return;
    setHotkeyBusy('toggle');
    setError('');
    try {
      const next = hotkeyStatus?.enabled ? await disableHotkey() : await enableHotkey();
      setHotkeyStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hotkey update failed');
    } finally {
      setHotkeyBusy('idle');
    }
  };

  const runHotkeyTest = async () => {
    if (hotkeyBusy !== 'idle') return;
    setHotkeyBusy('test');
    setError('');
    try {
      const result = await testHotkeyTrigger();
      setHotkeyStatus(result.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hotkey test failed');
    } finally {
      setHotkeyBusy('idle');
    }
  };

  const recording = status?.recording ?? false;
  const hotkeyActive = hotkeyStatus?.active ?? false;
  const latest = status?.latest;
  const intent = latest?.intent_preview;
  const selectedVoice = ttsVoices.find((voice) => voice.id === selectedVoiceId);
  const speaking = ttsStatus?.speaking ?? false;
  const buttonBusy = busy !== 'idle';
  const buttonLabel = recording ? 'Release to stop' : buttonBusy ? 'Working' : 'Hold to talk';
  const stateLabel = recording || hotkeyActive ? 'Recording' : busy === 'transcribing' ? 'Transcribing' : 'Idle';

  const speakTestPhrase = async () => {
    if (ttsBusy !== 'idle') return;
    setTtsBusy('speaking');
    setTtsError('');
    try {
      const response = await speakTTS('Siri voice output is local and ready.', selectedVoiceId, true);
      setTtsStatus(response.status);
      setSelectedVoiceId(response.status.selected_voice_id || selectedVoiceId);
    } catch (err) {
      setTtsError(err instanceof Error ? err.message : 'Speech failed');
    } finally {
      setTtsBusy('idle');
    }
  };

  const stopSpeaking = async () => {
    if (ttsBusy !== 'idle') return;
    setTtsBusy('stopping');
    setTtsError('');
    try {
      const response = await stopTTS();
      setTtsStatus(response.status);
    } catch (err) {
      setTtsError(err instanceof Error ? err.message : 'Stop speech failed');
    } finally {
      setTtsBusy('idle');
    }
  };

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

        <div
          className="mt-5 rounded-md border p-4"
          style={{
            borderColor: 'var(--color-border)',
            background: 'var(--color-bg-secondary)',
          }}
        >
          <div className="grid gap-3 md:grid-cols-3">
            <ContextTile
              icon={<Keyboard size={15} />}
              label="Global Trigger"
              value={hotkeyStatus?.effective_enabled ? 'Enabled' : hotkeyStatus?.enabled ? 'Privacy held' : 'Disabled'}
              detail={hotkeyStatus?.listener_running ? 'Listener active' : 'Listener idle'}
            />
            <ContextTile
              icon={<Power size={15} />}
              label="Binding"
              value={hotkeyStatus?.binding?.display_name || 'Fn'}
              detail={hotkeyStatus?.binding?.fallback_display_name || 'Ctrl+Space'}
            />
            <ContextTile
              icon={<ShieldCheck size={15} />}
              label="Last Trigger"
              value={hotkeyStatus?.active ? 'Pressed' : hotkeyStatus?.last_trigger?.phase || 'None'}
              detail={hotkeyStatus?.privacy_mode ? 'Privacy Mode' : hotkeyStatus?.last_trigger?.binding || 'Explicit only'}
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={toggleHotkey}
              disabled={hotkeyBusy !== 'idle' || hotkeyStatus?.privacy_mode}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-60"
              style={{
                borderColor: hotkeyStatus?.effective_enabled ? 'var(--color-success)' : 'var(--color-border)',
                color: 'var(--color-text)',
                background: 'var(--color-bg-primary)',
              }}
              title="Toggle global trigger"
            >
              <Keyboard size={16} />
              {hotkeyStatus?.enabled ? 'Disable' : 'Enable'}
            </button>
            <button
              type="button"
              onClick={runHotkeyTest}
              disabled={hotkeyBusy !== 'idle' || hotkeyStatus?.privacy_mode}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-60"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
                background: 'var(--color-bg-primary)',
              }}
              title="Test trigger"
            >
              <Play size={15} />
              Test
            </button>
            <button
              type="button"
              onClick={loadHotkeyStatus}
              className="flex h-10 w-10 items-center justify-center rounded-md border transition-colors"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-secondary)',
                background: 'var(--color-bg-primary)',
              }}
              title="Refresh global trigger"
            >
              <RefreshCw size={15} />
            </button>
            <StatusPill tone={hotkeyStatus?.active ? 'busy' : hotkeyStatus?.privacy_mode ? 'watch' : hotkeyStatus?.effective_enabled ? 'good' : 'quiet'}>
              {hotkeyStatus?.active ? 'Active' : hotkeyStatus?.privacy_mode ? 'Privacy off' : hotkeyStatus?.effective_enabled ? 'Ready' : 'Off'}
            </StatusPill>
          </div>
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

        <div
          className="mt-5 rounded-md border p-4"
          style={{
            borderColor: 'var(--color-border)',
            background: 'var(--color-bg-secondary)',
          }}
        >
          <div className="grid gap-3 md:grid-cols-3">
            <ContextTile
              icon={ttsStatus?.muted ? <VolumeX size={15} /> : <Volume2 size={15} />}
              label="Output"
              value={speaking ? 'Speaking' : ttsStatus?.muted ? 'Muted' : 'Ready'}
              detail={ttsStatus?.response_style || 'local voice'}
            />
            <ContextTile
              icon={<ShieldCheck size={15} />}
              label="TTS"
              value={ttsStatus?.local_only ? 'Local only' : 'Unavailable'}
              detail={ttsStatus?.cloud_tts_enabled ? 'Cloud enabled' : 'No cloud TTS'}
            />
            <ContextTile
              icon={<LockKeyhole size={15} />}
              label="Mode"
              value={ttsStatus?.privacy_mode ? 'Privacy' : ttsStatus?.quiet_mode ? 'Quiet' : ttsStatus?.active_mode_id || 'Mode'}
              detail={ttsStatus?.muted ? 'Quiet indicator' : 'Manual output'}
            />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <select
              value={selectedVoiceId}
              onChange={(event) => setSelectedVoiceId(event.target.value)}
              className="h-10 min-w-44 rounded-md border px-3 text-sm outline-none"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-primary)',
                color: 'var(--color-text)',
              }}
              aria-label="Selected voice"
            >
              {ttsVoices.map((voice) => (
                <option key={`${voice.engine}:${voice.id}`} value={voice.id}>
                  {voice.name} / {voice.engine}
                </option>
              ))}
              {!ttsVoices.length && <option value="">No local voice</option>}
            </select>
            <button
              type="button"
              onClick={speakTestPhrase}
              disabled={ttsBusy !== 'idle' || !ttsStatus?.available}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-60"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
                background: 'var(--color-bg-primary)',
              }}
              title="Speak test phrase"
            >
              <Volume2 size={16} />
              Test
            </button>
            <button
              type="button"
              onClick={stopSpeaking}
              disabled={ttsBusy !== 'idle' || !speaking}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-60"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text)',
                background: 'var(--color-bg-primary)',
              }}
              title="Stop speaking"
            >
              <Square size={15} />
              Stop
            </button>
            <button
              type="button"
              onClick={loadTtsStatus}
              className="flex h-10 w-10 items-center justify-center rounded-md border transition-colors"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-secondary)',
                background: 'var(--color-bg-primary)',
              }}
              title="Refresh voice output"
            >
              <RefreshCw size={15} />
            </button>
            <StatusPill tone={ttsStatus?.local_only ? 'good' : 'watch'}>
              {selectedVoice ? selectedVoice.engine : 'Local only'}
            </StatusPill>
          </div>
          {ttsError && (
            <p className="mt-3 text-sm" style={{ color: 'var(--color-error)' }}>
              {ttsError}
            </p>
          )}
        </div>
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
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [selected, setSelected] = useState<ResearchSession | null>(null);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [sources, setSources] = useState<ResearchSource[]>([]);
  const [memoryEntries, setMemoryEntries] = useState<StructuredMemory[]>([]);
  const [query, setQuery] = useState('local-first research workflow');
  const [status, setStatus] = useState<'loading' | 'ready' | 'offline' | 'running'>('loading');

  const loadResearch = async () => {
    setStatus('loading');
    try {
      const items = await listResearch(12);
      setSessions(items);
      setSelected((current) => current ?? items[0] ?? null);
      setStatus('ready');
    } catch {
      setSessions([]);
      setSelected(null);
      setReport(null);
      setSources([]);
      setMemoryEntries([]);
      setStatus('offline');
    }
  };

  useEffect(() => {
    loadResearch();
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!selected) {
      setReport(null);
      setSources([]);
      setMemoryEntries([]);
      return;
    }
    Promise.all([
      fetchResearchStatus(selected.id).catch(() => null),
      fetchResearchReport(selected.id).catch(() => selected.report),
      fetchResearchCitations(selected.id).catch(() => ({
        citations: selected.report?.citations ?? [],
        sources: selected.sources,
      })),
      fetchResearchMemoryEntries(selected.id).catch(() => []),
    ]).then(([nextStatus, nextReport, citationData, memories]) => {
      if (cancelled) return;
      setReport(nextReport);
      setSources(citationData.sources);
      setMemoryEntries(memories);
      if (nextStatus) setStatus('ready');
    });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const runResearch = async () => {
    if (!query.trim()) return;
    setStatus('running');
    try {
      const session = await startResearch({
        question: query.trim(),
        allow_external_search: false,
        max_sources: 8,
      });
      setSessions((items) => [session, ...items.filter((item) => item.id !== session.id)]);
      setSelected(session);
      setReport(session.report);
      setSources(session.sources);
      setStatus('ready');
    } catch {
      setStatus('offline');
    }
  };

  const activeReport = report ?? selected?.report ?? null;
  const activeSources = sources.length ? sources : selected?.sources ?? [];
  const openQuestions = activeReport?.unresolved_questions ?? selected?.plan.open_questions ?? [];
  const notes = activeReport?.notes ?? [];

  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Active Research" action={status}>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') runResearch();
            }}
            placeholder="Research question"
            className="min-w-0 flex-1 rounded-md border px-3 py-2 text-sm outline-none"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text)',
              background: 'var(--color-bg-secondary)',
            }}
          />
          <button
            type="button"
            onClick={runResearch}
            disabled={status === 'running' || !query.trim()}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border disabled:opacity-60"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            title="Start research"
          >
            {status === 'running' ? <RefreshCw size={16} /> : <Search size={16} />}
          </button>
        </div>

        <div className="mt-4 grid gap-2">
          {sessions.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              No research reports cached yet.
            </div>
          )}
          {sessions.slice(0, 8).map((session) => {
            const active = selected?.id === session.id;
            return (
              <button
                key={session.id}
                type="button"
                onClick={() => setSelected(session)}
                className="rounded-md border p-3 text-left transition-colors"
                style={{
                  borderColor: active ? 'var(--color-accent)' : 'var(--color-border)',
                  background: active ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
                  color: 'var(--color-text)',
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{session.question}</div>
                    <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      {session.sources.length} sources · {session.memory_ids.length} memories
                    </div>
                  </div>
                  <StatusPill tone={session.privacy_mode ? 'watch' : 'good'}>
                    {session.cached_sources_only ? 'Cached' : session.status}
                  </StatusPill>
                </div>
              </button>
            );
          })}
        </div>
      </ShellPanel>

      <div className="grid gap-4">
        <ShellPanel title={activeReport?.title || 'Report'} action={formatTime(activeReport?.created_at || selected?.created_at || '')}>
          {activeReport ? (
            <div className="grid gap-4">
              <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {activeReport.summary}
              </p>
              <div className="grid gap-3 md:grid-cols-3">
                {[
                  ['Notes', String(notes.length)],
                  ['Sources', String(activeSources.length)],
                  ['Citations', String(activeReport.citations.length)],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-md border p-3"
                    style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
                  >
                    <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{label}</div>
                    <div className="mt-1 text-xl font-semibold" style={{ color: 'var(--color-text)' }}>{value}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Select or start a research run.
            </p>
          )}
        </ShellPanel>

        <div className="grid gap-4 lg:grid-cols-2">
          <ShellPanel title="Notes" action={`${notes.length} claims`}>
            <div className="space-y-2">
              {notes.length === 0 && (
                <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  No extracted notes yet.
                </div>
              )}
              {notes.slice(0, 8).map((note) => (
                <div
                  key={note}
                  className="rounded-md border p-3 text-sm"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)', color: 'var(--color-text)' }}
                >
                  {note}
                </div>
              ))}
            </div>
          </ShellPanel>

          <ShellPanel title="Open Questions" action={`${openQuestions.length} unresolved`}>
            <div className="space-y-2">
              {openQuestions.map((question) => (
                <div
                  key={question}
                  className="rounded-md border p-3 text-sm"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)', color: 'var(--color-text-secondary)' }}
                >
                  {question}
                </div>
              ))}
            </div>
          </ShellPanel>
        </div>

        <ShellPanel title="Sources" action={`${activeSources.length} collected`}>
          <div className="grid gap-2">
            {activeSources.length === 0 && (
              <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                No cached sources matched.
              </div>
            )}
            {activeSources.slice(0, 8).map((source) => (
              <div
                key={source.id}
                className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_120px_90px]"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                    {source.title}
                  </div>
                  <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    {source.url || source.source_type}
                  </div>
                </div>
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {source.source_type}
                </span>
                <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {Math.round(source.relevance * 100)}%
                </span>
              </div>
            ))}
          </div>
        </ShellPanel>

        <ShellPanel title="Memory Entries" action={`${memoryEntries.length} stored`}>
          <div className="space-y-2">
            {memoryEntries.length === 0 && (
              <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                No stored research memories found.
              </div>
            )}
            {memoryEntries.slice(0, 5).map((memory) => (
              <div
                key={memory.id}
                className="rounded-md border p-3"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="truncate text-sm" style={{ color: 'var(--color-text)' }}>{memory.content}</div>
                <div className="mt-1 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  {memory.memory_type}
                </div>
              </div>
            ))}
          </div>
        </ShellPanel>
      </div>
    </div>
  );
}

function releaseTone(status: string): StatusTone {
  if (['ok', 'ready', 'completed'].includes(status)) return 'good';
  if (
    ['warning', 'needs_attention', 'completed_with_warnings', 'missing', 'blocked'].includes(status)
  )
    return 'watch';
  if (['loading', 'running'].includes(status)) return 'busy';
  return 'quiet';
}

function ReleaseSection() {
  const [snapshot, setSnapshot] = useState<ReleaseMissionControlSnapshot | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'offline'>('loading');
  const [acting, setActing] = useState<string>('');
  const [lastResult, setLastResult] = useState<ReleaseRecoveryResult | null>(null);

  const refreshRelease = async () => {
    setStatus('loading');
    try {
      setSnapshot(await fetchReleaseMissionControl());
      setStatus('ready');
    } catch {
      setSnapshot(null);
      setStatus('offline');
    }
  };

  useEffect(() => {
    refreshRelease();
  }, []);

  const runRepair = async (action: string) => {
    setActing(action);
    try {
      const result = await runReleaseRecoveryAction(action);
      setLastResult(result);
      await refreshRelease();
    } catch {
      setStatus('offline');
    } finally {
      setActing('');
    }
  };

  const healthChecks = snapshot?.health_checks ?? [];
  const diagnostics = snapshot?.diagnostics ?? [];
  const recoveryActions = snapshot?.recovery_actions ?? [];
  const report = snapshot?.report;
  const packaging = snapshot?.packaging_status;
  const installReadiness = snapshot?.install_readiness as
    | { ready?: boolean; blockers?: string[]; warnings?: string[] }
    | undefined;
  const installation = packaging?.installation as
    | {
        installed?: boolean;
        installed_locations?: string[];
        app_executable?: string;
        launch_agent?: { installed?: boolean; valid?: boolean; plist_path?: string };
      }
    | undefined;
  const score = report?.readiness_score ?? 0;
  const warnings = report?.warnings ?? [];

  return (
    <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <ShellPanel
        title="Release Health"
        action={status === 'loading' ? 'loading' : status === 'offline' ? 'offline' : report?.readiness_status}
      >
        <div className="grid gap-4">
          <div className="grid gap-3 md:grid-cols-4">
            <div
              className="rounded-md border p-4"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                Readiness
              </div>
              <div className="mt-2 flex items-end gap-2">
                <span className="text-3xl font-semibold" style={{ color: 'var(--color-text)' }}>
                  {score}
                </span>
                <span className="pb-1 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  / 100
                </span>
              </div>
            </div>
            <div
              className="rounded-md border p-4"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                Privacy
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusPill tone={snapshot?.local_only ? 'good' : 'watch'}>Local only</StatusPill>
                <StatusPill tone={snapshot?.telemetry_enabled ? 'watch' : 'good'}>No telemetry</StatusPill>
              </div>
            </div>
            <div
              className="rounded-md border p-4"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                Scope
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusPill tone={snapshot?.wake_words ? 'watch' : 'good'}>{snapshot?.wake_words ? 'Listening for Wake Word' : 'No wake words'}</StatusPill>
                <StatusPill tone={snapshot?.autonomous_agents ? 'watch' : 'good'}>No agents</StatusPill>
              </div>
            </div>
            <div
              className="rounded-md border p-4"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
            >
              <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                Install
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusPill tone={installReadiness?.ready ? 'good' : 'watch'}>
                  {installReadiness?.ready ? 'Ready' : `${installReadiness?.blockers?.length ?? 0} blockers`}
                </StatusPill>
                <StatusPill tone={installation?.installed ? 'good' : 'quiet'}>
                  {installation?.installed ? 'Installed' : 'Not installed'}
                </StatusPill>
              </div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <ContextTile
              icon={<Package size={14} />}
              label="Siri.app"
              value={
                installation?.installed_locations?.length
                  ? compactPath(installation.installed_locations[0])
                  : compactPath(String(packaging?.app_bundle_path || ''))
              }
              detail={packaging?.app_bundle_exists ? 'Bundle built' : 'Bundle not built'}
            />
            <ContextTile
              icon={<Power size={14} />}
              label="LaunchAgent"
              value={
                installation?.launch_agent?.installed
                  ? installation.launch_agent.valid
                    ? 'Installed'
                    : 'Needs update'
                  : 'Not installed'
              }
              detail={compactPath(installation?.launch_agent?.plist_path || '')}
            />
            <ContextTile
              icon={<TerminalSquare size={14} />}
              label="Executable"
              value={basename(installation?.app_executable || '') || 'Unavailable'}
              detail={compactPath(installation?.app_executable || '')}
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {healthChecks.map((check) => (
              <div
                key={check.id}
                className="rounded-md border p-4"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                      {check.label}
                    </div>
                    <p className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      {check.summary}
                    </p>
                    {check.detail && (
                      <p className="mt-2 truncate text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                        {check.detail}
                      </p>
                    )}
                  </div>
                  <StatusPill tone={releaseTone(check.status)}>{check.status}</StatusPill>
                </div>
              </div>
            ))}
          </div>
        </div>
      </ShellPanel>

      <div className="grid gap-4">
        <ShellPanel title="Diagnostics Summary" action={`${diagnostics.length} checks`}>
          <div className="space-y-2">
            {diagnostics.map((item) => (
              <div
                key={item.id}
                className="rounded-md border p-3"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                    {item.label}
                  </span>
                  <StatusPill tone={releaseTone(item.status)}>{item.status}</StatusPill>
                </div>
                <p className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {item.summary}
                </p>
              </div>
            ))}
          </div>
        </ShellPanel>

        <ShellPanel title="Repair Actions" action="explicit">
          <div className="grid gap-2">
            {recoveryActions.map((action) => (
              <button
                key={action.id}
                type="button"
                disabled={!!acting}
                onClick={() => runRepair(action.id)}
                className="flex items-center justify-between gap-3 rounded-md border px-3 py-3 text-left text-sm transition-colors disabled:opacity-50"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text)',
                  background: 'var(--color-bg-secondary)',
                }}
                title={action.description}
              >
                <span className="flex min-w-0 items-center gap-2">
                  {acting === action.id ? <RefreshCw size={15} /> : <Wrench size={15} />}
                  <span className="truncate">{acting === action.id ? 'Running' : action.label}</span>
                </span>
                <ArrowUpRight size={14} />
              </button>
            ))}
          </div>
          {lastResult && (
            <div className="mt-3 rounded-md border p-3" style={{ borderColor: 'var(--color-border)' }}>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                  {lastResult.action}
                </span>
                <StatusPill tone={releaseTone(lastResult.status)}>{lastResult.status}</StatusPill>
              </div>
              <p className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {lastResult.summary}
              </p>
            </div>
          )}
        </ShellPanel>

        <ShellPanel title="Warnings" action={`${warnings.length} active`}>
          <div className="space-y-2">
            {warnings.length === 0 ? (
              <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                <CheckCircle2 size={16} style={{ color: 'var(--color-success)' }} />
                Release checks are quiet
              </div>
            ) : (
              warnings.slice(0, 5).map((warning) => (
                <div key={warning} className="flex items-start gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  <AlertTriangle size={14} style={{ color: 'var(--color-warning)' }} />
                  <span>{warning}</span>
                </div>
              ))
            )}
          </div>
        </ShellPanel>
      </div>
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

function PersonalizationSection() {
  const [status, setStatus] = useState<ProfileStatus | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const [s, p] = await Promise.all([
        fetchPersonalizationStatus(),
        listProfiles()
      ]);
      setStatus(s);
      setProfiles(p);
    } catch {
      // fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const switchProfile = async (id: string) => {
    try {
      await switchActiveProfile(id);
      refresh();
    } catch {
      // ignore
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>Loading personalization...</div>;
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
      <ShellPanel title="Active Profile" action={status?.active_profile?.name || 'Unknown'}>
        <div className="grid gap-3">
          <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            Switch Profile
          </div>
          <div className="flex flex-wrap gap-2">
            {profiles.map(p => (
              <button
                key={p.id}
                type="button"
                onClick={() => switchProfile(p.id)}
                className={`rounded-md border px-3 py-2 text-sm transition-colors ${p.id === status?.active_profile_id ? 'font-bold' : ''}`}
                style={{
                  borderColor: p.id === status?.active_profile_id ? 'var(--color-accent)' : 'var(--color-border)',
                  background: p.id === status?.active_profile_id ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
                  color: 'var(--color-text)'
                }}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>
      </ShellPanel>

      <ShellPanel title="Preferences">
        <div className="grid gap-3 md:grid-cols-2">
          {[
            ['Preferred Workspace', status?.preferences?.preferred_workspace || 'Default'],
            ['Agent Preference', status?.preferences?.coding_vs_engineering_preference || 'Balanced'],
            ['Voice Interaction', status?.preferences?.voice_interaction ? 'Enabled' : 'Disabled'],
            ['Wake Word', status?.preferences?.wake_word_preference ? 'Enabled' : 'Disabled'],
            ['Quiet Mode', status?.preferences?.quiet_mode ? 'Enabled' : 'Disabled']
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

function ActiveSection({ section }: { section: MissionSectionId }) {
  if (section === 'today') return <TodaySection />;
  if (section === 'world-map') return <WorldMapSection />;
  if (section === 'daily-briefing') return <DailyBriefingSection />;
  if (section === 'important-events') return <ImportantEventsSection />;
  if (section === 'tasks') return <TasksSection />;
  if (section === 'agents') return <AgentsSection />;
  if (section === 'memory') return <MemorySection />;
  if (section === 'projects') return <ProjectsSection />;
  if (section === 'desktop') return <DesktopSection />;
  if (section === 'engineering') return <EngineeringSection />;
  if (section === 'coding') return <CodingSection />;
  if (section === 'repo') return <RepoSection />;
  if (section === 'voice') return <VoiceSection />;
  if (section === 'vision') return <VisionSection />;
  if (section === 'terminal') return <TerminalSection />;
  if (section === 'workflows') return <WorkflowsSection />;
  if (section === 'research') return <ResearchSection />;
  if (section === 'learning') return <LearningPanel />;
  if (section === 'release') return <ReleaseSection />;
  if (section === 'settings') return <SettingsSection />;
  if (section === 'personalization') return <PersonalizationSection />;
  if (section === 'permissions') return <PermissionsSection />;
  if (section === 'autonomy') return <AutonomySection />;
  return <HomeSection />;
}

function AutonomySection() {
  const [approvals, setApprovals] = useState<AutonomyApprovalRequest[]>([]);
  const [live, setLive] = useState(false);
  const [goalTitle, setGoalTitle] = useState('');
  const [goalDesc, setGoalDesc] = useState('');
  const [activeGoal, setActiveGoal] = useState<AutonomyGoal | null>(null);
  const [plan, setPlan] = useState<AutonomyPlan | null>(null);
  const [state, setState] = useState<AutonomyExecutionState | null>(null);

  const loadApprovals = async () => {
    try {
      const data = await fetchAutonomyApprovals();
      setApprovals(data);
      setLive(true);
    } catch {
      setLive(false);
    }
  };

  useEffect(() => {
    loadApprovals();
    const interval = setInterval(loadApprovals, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCreateGoal = async () => {
    if (!goalTitle || !goalDesc) return;
    try {
      const g = await createAutonomyGoal(goalTitle, goalDesc);
      setActiveGoal(g);
      setGoalTitle('');
      setGoalDesc('');
    } catch (err) {
      console.error(err);
    }
  };

  const handleGeneratePlan = async () => {
    if (!activeGoal) return;
    try {
      const p = await generateAutonomyPlan(activeGoal.id);
      setPlan(p);
    } catch (err) {
      console.error(err);
    }
  };

  const handleStart = async () => {
    if (!plan) return;
    try {
      const s = await startAutonomyPlan(plan.id);
      setState(s);
    } catch (err) {
      console.error(err);
    }
  };

  const handlePause = async () => {
    if (!plan) return;
    try {
      const s = await pauseAutonomyPlan(plan.id);
      setState(s);
    } catch (err) {
      console.error(err);
    }
  };

  const handleResume = async () => {
    if (!plan) return;
    try {
      const s = await resumeAutonomyPlan(plan.id);
      setState(s);
    } catch (err) {
      console.error(err);
    }
  };

  const handleStop = async () => {
    if (!plan) return;
    try {
      const s = await stopAutonomyPlan(plan.id);
      setState(s);
    } catch (err) {
      console.error(err);
    }
  };

  const handleResolve = async (id: string, approved: boolean) => {
    try {
      await resolveAutonomyApproval(id, approved);
      loadApprovals();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <ShellPanel title="Autonomy Controls" action={live ? 'live' : 'offline'}>
        <div className="space-y-4">
          <div className="rounded-md border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
            <h3 className="mb-2 text-sm font-semibold">1. Set Goal</h3>
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Goal Title"
                value={goalTitle}
                onChange={(e) => setGoalTitle(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm outline-none"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              />
              <textarea
                placeholder="Goal Description"
                value={goalDesc}
                onChange={(e) => setGoalDesc(e.target.value)}
                className="w-full rounded-md border px-3 py-2 text-sm outline-none"
                rows={3}
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              />
              <button
                type="button"
                onClick={handleCreateGoal}
                className="rounded-md border px-3 py-2 text-sm font-medium transition-colors"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-accent-subtle)', color: 'var(--color-text)' }}
              >
                Create Goal
              </button>
            </div>
            {activeGoal && (
              <div className="mt-4 border-t pt-4" style={{ borderColor: 'var(--color-border)' }}>
                <div className="text-sm font-medium">Current Goal: {activeGoal.title}</div>
                <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{activeGoal.status}</div>
                <button
                  type="button"
                  onClick={handleGeneratePlan}
                  className="mt-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                >
                  Generate Plan
                </button>
              </div>
            )}
          </div>

          {plan && (
            <div className="rounded-md border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <h3 className="mb-2 text-sm font-semibold">2. Execution</h3>
              <div className="mb-4 flex gap-2">
                <button
                  onClick={handleStart}
                  className="rounded-md border px-3 py-1 text-xs font-medium"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-success)', color: '#fff' }}
                >
                  Start
                </button>
                <button
                  onClick={handlePause}
                  className="rounded-md border px-3 py-1 text-xs font-medium"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-warning)', color: '#fff' }}
                >
                  Pause
                </button>
                <button
                  onClick={handleResume}
                  className="rounded-md border px-3 py-1 text-xs font-medium"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-accent)', color: '#fff' }}
                >
                  Resume
                </button>
                <button
                  onClick={handleStop}
                  className="rounded-md border px-3 py-1 text-xs font-medium"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-error)', color: '#fff' }}
                >
                  Stop
                </button>
              </div>
              <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                Status: {state?.status || 'idle'} <br />
                Step: {state?.current_step_id || 'none'}
              </div>
              <div className="mt-4 space-y-2">
                {plan.steps.map(step => (
                  <div key={step.id} className="rounded-md border p-2 text-xs" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)' }}>
                    <div className="font-semibold">{step.title}</div>
                    <div style={{ color: 'var(--color-text-tertiary)' }}>{step.action_type} - {step.status}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </ShellPanel>

      <ShellPanel title="Approval Queue" action={`${approvals.length} pending`}>
        <div className="space-y-3">
          {approvals.map(app => (
            <div key={app.id} className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold">Step Approval</span>
                <StatusPill tone="watch">Pending</StatusPill>
              </div>
              <div className="mb-3 text-xs" style={{ color: 'var(--color-text-secondary)' }}>{app.reason}</div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleResolve(app.id, true)}
                  className="rounded-md border px-3 py-1 text-xs font-medium"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-success)', color: '#fff' }}
                >
                  Approve
                </button>
                <button
                  onClick={() => handleResolve(app.id, false)}
                  className="rounded-md border px-3 py-1 text-xs font-medium"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-error)', color: '#fff' }}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
          {approvals.length === 0 && (
            <div className="rounded-md border p-3 text-sm" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-tertiary)' }}>
              No pending approvals.
            </div>
          )}
        </div>
      </ShellPanel>
    </div>
  );
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
