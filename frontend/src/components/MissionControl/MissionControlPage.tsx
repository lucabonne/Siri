import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  AppWindow,
  ArrowUpRight,
  Ban,
  BookMarked,
  Brain,
  Camera,
  CheckCircle2,
  Circle,
  Clock3,
  Clipboard,
  Code2,
  Cpu,
  Eye,
  FileDown,
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
  cancelVoiceSession,
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
  submitVoiceTranscript,
  switchActiveWorkspaceAgent,
  switchActiveSiriMode,
  triggerStartupMorningBriefing,
  syncWorldMonitor,
  dispatchVoiceTranscript,
  fetchKnowledgeNotes,
  createKnowledgeNote,
  deleteKnowledgeNote,
  pinKnowledgeNote,
  fetchVaultTags,
  getDailyNote,
  searchKnowledgeVault,
  exportVault,
  fetchKnowledgeGraphStatus,
  fetchGraphRoots,
  fetchKnowledgeTimeline,
  searchKnowledgeNeighborhood,
  fetchGraphTraversal,
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
  VoiceStackStatus,
  VoiceSubmitTranscriptResponse,
  VoiceDispatchResponse,
  WorkspaceAgentConfig,
  CodingPanelSnapshot,
  BriefingStatus,
  DailyBriefing,
  MorningEvent,
  StartupStatus,
  WorldMonitorStatus,
  WorldMonitorSyncStatus,
} from '../../lib/api';
import type {
  KnowledgeNote,
  KnowledgeNoteListItem,
  VaultTag,
  KnowledgeGraphEdge,
  KnowledgeGraphNeighborhood,
  KnowledgeGraphNode,
  KnowledgeGraphStatus,
  KnowledgeNeighborhoodSearchResult,
  KnowledgeTimelineEvent,
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

function ShellPanel({
  title,
  action,
  children,
  className = '',
  style,
}: {
  title: string;
  action?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <section className={`hud-panel p-4 ${className}`} style={style}>
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

function formatVoiceDuration(value: number | null | undefined): string {
  return value && value > 0 ? `${value}s` : 'Requires --duration';
}

function modelPathStatus(model: VoiceStackStatus['model_path'] | undefined): string {
  if (!model) return 'Unknown';
  if (!model.required) return 'Not required';
  if (model.exists === true) return 'Found';
  if (model.exists === false) return 'Missing';
  return 'Required';
}

function configuredVoiceValue(value: string | undefined, fallback = 'Not configured'): string {
  return value && value.trim() ? value : fallback;
}

type VoiceSetupChecklistItem = {
  label: string;
  value: string;
  detail: string;
  tone: StatusTone;
  manualCommands?: Array<{
    command: string;
    detail: string;
  }>;
};

type VoiceManualCommand = {
  label: string;
  command: string;
  detail: string;
  tone: StatusTone;
};

type VoiceDiagnosticsSummaryItem = {
  label: string;
  value: string;
  detail: string;
  tone: StatusTone;
};

type VoiceSafetyAuditSummaryItem = VoiceDiagnosticsSummaryItem;

type VoiceSetupTroubleshootingItem = {
  label: string;
  reason: string;
  hint: string;
  tone: StatusTone;
  manualReference?: string;
};

function voiceReadinessTone(state: string | undefined): StatusTone {
  if (state === 'ready') return 'good';
  if (state === 'unsafe_config') return 'watch';
  if (state === 'needs_setup') return 'busy';
  return 'quiet';
}

function voiceReadinessLabel(state: string | undefined): string {
  if (state === 'ready') return 'Ready';
  if (state === 'needs_setup') return 'Needs setup';
  if (state === 'unsafe_config') return 'Unsafe config';
  return 'Unknown';
}

function voiceChecklistTone(ready: boolean, pendingTone: StatusTone = 'watch'): StatusTone {
  return ready ? 'good' : pendingTone;
}

function enabledLabel(value: boolean | undefined): string {
  if (typeof value === 'undefined') return 'Unknown';
  return value ? 'Enabled' : 'Disabled';
}

function yesNoLabel(value: boolean | undefined): string {
  if (typeof value === 'undefined') return 'Unknown';
  return value ? 'Yes' : 'No';
}

function auditEnabledLabel(value: boolean | undefined, enabled = 'Enabled', disabled = 'Disabled'): string {
  if (typeof value === 'undefined') return 'Unknown';
  return value ? enabled : disabled;
}

function copyManualCommand(command: string) {
  if (typeof navigator === 'undefined' || !navigator.clipboard) return;
  void navigator.clipboard.writeText(command).catch(() => {});
}

function voiceSetupCommandAdapter(stack: VoiceStackStatus | undefined): string {
  if (
    stack?.transcription_adapter.supported
    && stack.transcription_adapter.effective
    && stack.transcription_adapter.effective !== 'disabled'
  ) {
    return stack.transcription_adapter.effective;
  }
  return 'faster-whisper';
}

function voiceSetupCommandDuration(stack: VoiceStackStatus | undefined): number {
  const duration = stack?.record_duration.effective_default_seconds;
  return duration && duration > 0 ? duration : 2;
}

function voiceKnownCommandAdapter(stack: VoiceStackStatus | undefined): string {
  if (
    stack?.transcription_adapter.supported
    && stack.transcription_adapter.effective
    && stack.transcription_adapter.effective !== 'disabled'
  ) {
    return stack.transcription_adapter.effective;
  }
  return '';
}

function voiceRunLocalBaseCommand(stack: VoiceStackStatus | undefined): string {
  const duration = voiceSetupCommandDuration(stack);
  const adapter = voiceKnownCommandAdapter(stack);
  return [
    'jarvis voice run-local',
    '--duration',
    String(duration),
    adapter ? `--adapter ${adapter}` : '',
  ].filter(Boolean).join(' ');
}

function buildVoicePipelineManualCommands(stack: VoiceStackStatus | undefined): VoiceManualCommand[] {
  const baseCommand = voiceRunLocalBaseCommand(stack);
  return [
    {
      label: 'Preview only',
      command: baseCommand,
      detail: 'Manual terminal command. Records/transcribes locally and submits preview; dispatch and speech stay off.',
      tone: 'good',
    },
    {
      label: 'Approve dispatch',
      command: `${baseCommand} --approve-dispatch`,
      detail: 'Manual explicit terminal command. Dispatch happens only after this approval flag is included.',
      tone: 'watch',
    },
    {
      label: 'Approve dispatch + speak',
      command: `${baseCommand} --approve-dispatch --speak-result`,
      detail: 'Manual explicit terminal command. Speech happens only for the dispatch result after explicit approval.',
      tone: 'watch',
    },
  ];
}

function voiceSetupManualCommands(stack: VoiceStackStatus | undefined) {
  const adapter = voiceSetupCommandAdapter(stack);
  const duration = voiceSetupCommandDuration(stack);
  return {
    doctor: {
      command: 'jarvis voice doctor',
      detail: 'Inspect local voice setup without recording, dispatching, speaking, or starting hotkeys.',
    },
    transcribeFile: {
      command: `jarvis voice transcribe-file ./voice-sample.wav --adapter ${adapter}`,
      detail: 'Transcribe an existing local WAV with an explicit local adapter.',
    },
    recordLocal: {
      command: `jarvis voice record-local --duration ${duration}`,
      detail: 'Record a fixed-duration local WAV only; no transcription, dispatch, or speech.',
    },
    hotkeyBridge: {
      command: `jarvis voice hotkey-bridge --adapter ${adapter}`,
      detail: 'Print the disabled bridge command/example only; no global listener is started.',
    },
    runLocal: {
      command: `jarvis voice run-local --duration ${duration} --adapter ${adapter}`,
      detail: 'Run the explicit preview-only local pipeline; dispatch and speech stay off.',
    },
  };
}

function buildVoiceSetupChecklist(
  status: VoicePttStatus | null,
  stack: VoiceStackStatus | undefined,
): VoiceSetupChecklistItem[] {
  const commands = voiceSetupManualCommands(stack);
  const hasApiBase = Boolean(stack?.api_base_url.value);
  const adapterSelected = Boolean(
    stack?.transcription_adapter.effective
      && stack.transcription_adapter.effective !== 'disabled'
      && stack.transcription_adapter.supported,
  );
  const modelConfigured = Boolean(stack?.model_path.value);
  const modelExistsReady = !stack?.model_path.required || stack.model_path.exists === true;
  const recorderBoundaryAvailable = Boolean(status?.push_to_talk_only)
    && status?.passive_listening === false;
  const speechBackendReady = Boolean(
    stack?.speech_output.effective && stack.speech_output.supported,
  );
  const hotkeyBridgeSafe = Boolean(stack?.hotkey_bridge.print_only)
    && stack?.hotkey_bridge.enabled === false
    && stack?.hotkey_bridge.listener_started === false
    && stack?.hotkey_bridge.global_key_capture === false;
  const approvalRequired = stack?.approval.required ?? status?.requires_explicit_approval ?? false;
  const fullTranscriptLoggingEnabled = stack?.recent_events.include_full_transcripts ?? false;

  return [
    {
      label: 'API base URL configured',
      value: hasApiBase ? 'Configured' : 'Missing',
      detail: stack?.api_base_url.source || 'Voice status not loaded',
      tone: voiceChecklistTone(hasApiBase),
      manualCommands: hasApiBase ? undefined : [commands.doctor],
    },
    {
      label: 'Transcription adapter selected',
      value: adapterSelected ? stack?.transcription_adapter.effective || 'Selected' : 'Missing',
      detail: stack?.transcription_adapter.source || 'Local transcription disabled',
      tone: voiceChecklistTone(adapterSelected),
      manualCommands: adapterSelected ? undefined : [commands.transcribeFile, commands.runLocal],
    },
    {
      label: 'Model path configured',
      value: modelConfigured ? 'Configured' : 'Missing',
      detail: stack?.model_path.value ? compactPath(stack.model_path.value) : 'No model path configured',
      tone: voiceChecklistTone(modelConfigured),
      manualCommands: modelConfigured ? undefined : [commands.doctor, commands.transcribeFile],
    },
    {
      label: 'Model path exists',
      value: !stack?.model_path.required
        ? 'Not required'
        : stack.model_path.exists
          ? 'Found'
          : 'Missing',
      detail: stack?.model_path.source || 'No model source',
      tone: stack?.model_path.required ? voiceChecklistTone(modelExistsReady) : 'quiet',
      manualCommands: stack?.model_path.required && !modelExistsReady
        ? [commands.doctor, commands.transcribeFile]
        : undefined,
    },
    {
      label: 'Recorder boundary available',
      value: recorderBoundaryAvailable ? 'Available' : 'Pending',
      detail: status ? 'Live capture remains deferred' : 'Voice status not loaded',
      tone: voiceChecklistTone(recorderBoundaryAvailable),
      manualCommands: recorderBoundaryAvailable ? undefined : [commands.recordLocal],
    },
    {
      label: 'Speech output backend configured',
      value: speechBackendReady ? stack?.speech_output.effective || 'Configured' : 'Missing',
      detail: configuredVoiceValue(stack?.speech_output.configured, 'Default adapter'),
      tone: voiceChecklistTone(speechBackendReady),
      manualCommands: speechBackendReady ? undefined : [commands.doctor],
    },
    {
      label: 'macOS say availability',
      value: stack?.macos_say.relevant
        ? stack.macos_say.available
          ? 'Available'
          : 'Unavailable'
        : 'Not selected',
      detail: stack?.macos_say.relevant ? 'Relevant backend' : 'Not required for selected backend',
      tone: stack?.macos_say.relevant
        ? voiceChecklistTone(stack.macos_say.available)
        : 'quiet',
      manualCommands: stack?.macos_say.relevant && !stack.macos_say.available
        ? [commands.doctor]
        : undefined,
    },
    {
      label: 'Hotkey bridge disabled/print-only',
      value: hotkeyBridgeSafe ? 'Safe' : 'Check required',
      detail: stack?.hotkey_bridge.print_only ? 'Print-only preview' : 'Listener state unknown',
      tone: voiceChecklistTone(hotkeyBridgeSafe),
      manualCommands: hotkeyBridgeSafe ? undefined : [commands.hotkeyBridge],
    },
    {
      label: 'Approval required',
      value: approvalRequired ? 'Required' : 'Not required',
      detail: stack?.approval.config || 'Voice approval status pending',
      tone: voiceChecklistTone(approvalRequired),
      manualCommands: approvalRequired ? undefined : [commands.doctor],
    },
    {
      label: 'Full transcript logging',
      value: fullTranscriptLoggingEnabled ? 'Enabled' : 'Disabled',
      detail: stack?.recent_events.enabled ? 'Local voice event logging configured' : 'Local voice event logging unavailable',
      tone: fullTranscriptLoggingEnabled ? 'watch' : 'good',
    },
  ];
}

function buildVoiceDiagnosticsSummary(
  status: VoicePttStatus | null,
  stack: VoiceStackStatus | undefined,
): VoiceDiagnosticsSummaryItem[] {
  const modelConfigured = Boolean(stack?.model_path.value);
  const modelExistsReady = !stack?.model_path.required || stack.model_path.exists === true;
  const hotkeyBridgeSafe = Boolean(stack?.hotkey_bridge.print_only)
    && stack?.hotkey_bridge.enabled === false
    && stack?.hotkey_bridge.listener_started === false
    && stack?.hotkey_bridge.global_key_capture === false;
  const approvalRequired = stack?.approval.required ?? status?.requires_explicit_approval;

  return [
    {
      label: 'API base URL',
      value: stack?.api_base_url.value || 'Unknown',
      detail: stack?.api_base_url.source || 'Voice status not loaded',
      tone: stack?.api_base_url.value ? 'quiet' : 'watch',
    },
    {
      label: 'Transcription adapter',
      value: stack?.transcription_adapter.effective || 'Unknown',
      detail: configuredVoiceValue(stack?.transcription_adapter.configured),
      tone: stack?.transcription_adapter.supported ? 'good' : 'watch',
    },
    {
      label: 'Model path configured',
      value: modelConfigured ? 'Configured' : 'Missing',
      detail: stack?.model_path.value ? compactPath(stack.model_path.value) : 'No model path configured',
      tone: voiceChecklistTone(modelConfigured),
    },
    {
      label: 'Model path exists',
      value: modelPathStatus(stack?.model_path),
      detail: stack?.model_path.source || 'No model source',
      tone: stack?.model_path.required ? voiceChecklistTone(modelExistsReady) : 'quiet',
    },
    {
      label: 'Default record duration',
      value: stack ? formatVoiceDuration(stack.record_duration.effective_default_seconds) : 'Unknown',
      detail: stack
        ? stack.record_duration.duration_flag_required ? 'CLI flag required' : 'Configured default'
        : 'Voice status not loaded',
      tone: stack?.record_duration.duration_flag_required ? 'watch' : stack ? 'good' : 'watch',
    },
    {
      label: 'Speech output backend',
      value: stack?.speech_output.backend || stack?.speech_output.effective || 'Unknown',
      detail: configuredVoiceValue(stack?.speech_output.configured, 'Default adapter'),
      tone: stack?.speech_output.supported ? 'good' : 'watch',
    },
    {
      label: 'macOS say availability',
      value: yesNoLabel(stack?.macos_say.available),
      detail: stack?.macos_say.path ? compactPath(stack.macos_say.path) : stack?.macos_say.relevant ? 'No say binary found' : 'Not selected',
      tone: stack?.macos_say.relevant ? voiceChecklistTone(stack.macos_say.available === true) : 'quiet',
    },
    {
      label: 'Hotkey bridge',
      value: hotkeyBridgeSafe ? 'Disabled / print-only' : 'Check required',
      detail: stack?.hotkey_bridge.listener_started || stack?.hotkey_bridge.global_key_capture
        ? 'Listener or global capture reported'
        : 'No listener started',
      tone: voiceChecklistTone(hotkeyBridgeSafe),
    },
    {
      label: 'Approval required',
      value: yesNoLabel(approvalRequired),
      detail: stack?.approval.config || 'Voice approval status pending',
      tone: approvalRequired ? 'good' : 'watch',
    },
    {
      label: 'Logging',
      value: enabledLabel(stack?.recent_events.enabled),
      detail: stack?.recent_events.enabled ? 'Recent event metadata available' : 'Local voice event logging disabled',
      tone: stack?.recent_events.enabled ? 'quiet' : 'watch',
    },
    {
      label: 'Full transcript logging',
      value: enabledLabel(stack?.recent_events.include_full_transcripts),
      detail: stack?.recent_events.include_full_transcripts ? 'Transcript body may exist in local logs' : 'Redacted summaries only',
      tone: stack?.recent_events.include_full_transcripts ? 'watch' : 'good',
    },
  ];
}

function buildVoiceSetupTroubleshooting(
  status: VoicePttStatus | null,
  stack: VoiceStackStatus | undefined,
): VoiceSetupTroubleshootingItem[] {
  const commands = voiceSetupManualCommands(stack);
  const items: VoiceSetupTroubleshootingItem[] = [];

  if (!stack) {
    return [
      {
        label: 'Voice status',
        reason: status ? 'Voice stack details were not returned by the status endpoint.' : 'Voice status has not loaded yet.',
        hint: 'Refresh status or run the existing CLI diagnostics manually in a terminal.',
        tone: 'watch',
        manualReference: commands.doctor.command,
      },
    ];
  }

  if (!stack.api_base_url.value) {
    items.push({
      label: 'API base URL missing',
      reason: 'The voice CLI/status flow does not have an effective OpenJarvis API base URL.',
      hint: 'Set `OPENJARVIS_BASE_URL` or `[voice_control].default_api_base_url` before running manual terminal commands.',
      tone: 'watch',
      manualReference: commands.doctor.command,
    });
  }

  const adapterSelected = Boolean(
    stack.transcription_adapter.effective
      && stack.transcription_adapter.effective !== 'disabled'
      && stack.transcription_adapter.supported,
  );
  if (!adapterSelected) {
    items.push({
      label: 'No transcription adapter selected',
      reason: stack.transcription_adapter.effective
        ? `Effective adapter "${stack.transcription_adapter.effective}" is not supported for local voice transcription.`
        : 'Local voice transcription is disabled or not configured.',
      hint: 'Choose a local adapter with a CLI flag or `[voice_control].transcription_adapter`; Mission Control only reports the current value.',
      tone: 'watch',
      manualReference: commands.transcribeFile.command,
    });
  }

  if (stack.model_path.required && !stack.model_path.value) {
    items.push({
      label: 'Model path missing',
      reason: 'The selected local transcription adapter requires a model path or supported model name.',
      hint: 'Set the model path in config or pass the adapter/model through an explicit terminal command before transcription.',
      tone: 'watch',
      manualReference: commands.doctor.command,
    });
  }

  if (stack.model_path.required && stack.model_path.value && stack.model_path.exists === false) {
    items.push({
      label: 'Model path does not exist',
      reason: `${compactPath(stack.model_path.value)} was configured but was not found on disk.`,
      hint: 'Point the config or environment variable at an existing local model path; Mission Control will not create or download it.',
      tone: 'watch',
      manualReference: commands.doctor.command,
    });
  }

  const recorderBoundaryAvailable = Boolean(status?.push_to_talk_only)
    && status?.passive_listening === false;
  if (!recorderBoundaryAvailable) {
    items.push({
      label: 'Recorder boundary pending',
      reason: status ? 'The status payload does not confirm push-to-talk-only capture with passive listening disabled.' : 'Voice status is not loaded.',
      hint: 'Use explicit fixed-duration recorder commands manually; Mission Control does not start microphone capture.',
      tone: 'watch',
      manualReference: commands.recordLocal.command,
    });
  }

  if (!stack.speech_output.effective || !stack.speech_output.supported) {
    items.push({
      label: 'Speech backend unavailable',
      reason: stack.speech_output.effective
        ? `Configured speech backend "${stack.speech_output.effective}" is not supported here.`
        : 'No speech output backend is available.',
      hint: 'Use explicit `jarvis voice speak` only after selecting a supported local speech output adapter.',
      tone: 'watch',
      manualReference: 'jarvis voice speak "preview complete"',
    });
  }

  if (stack.macos_say.relevant && !stack.macos_say.available) {
    items.push({
      label: 'macOS say unavailable',
      reason: '`macos-say` is selected, but the local `say` executable was not found for this system.',
      hint: 'Use another supported explicit speech output adapter when available, or run CLI diagnostics manually.',
      tone: 'watch',
      manualReference: commands.doctor.command,
    });
  }

  const hotkeyBridgeSafe = stack.hotkey_bridge.print_only
    && stack.hotkey_bridge.enabled === false
    && stack.hotkey_bridge.listener_started === false
    && stack.hotkey_bridge.global_key_capture === false;
  items.push({
    label: 'Hotkey bridge disabled/print-only',
    reason: hotkeyBridgeSafe
      ? 'This is intentional: Mission Control does not enable Fn/global hotkey capture or start a listener.'
      : 'The reported bridge state is not the expected disabled, print-only boundary.',
    hint: 'Use the hotkey bridge command only as a manual terminal preview; granting Accessibility permission and installing helpers remain external steps.',
    tone: hotkeyBridgeSafe ? 'quiet' : 'watch',
    manualReference: commands.hotkeyBridge.command,
  });

  const approvalRequired = stack.approval.required ?? status?.requires_explicit_approval;
  if (!approvalRequired) {
    items.push({
      label: 'Approval requirement missing',
      reason: 'The current status does not report explicit approval as required before dispatch.',
      hint: 'Keep dispatch on the manual `--approve-dispatch` path; Mission Control does not bypass or grant approval.',
      tone: 'watch',
      manualReference: commands.doctor.command,
    });
  }

  if (!stack.recent_events.enabled) {
    items.push({
      label: 'Logging disabled',
      reason: 'Local voice event logging is disabled, so recent diagnostic/event history is unavailable.',
      hint: 'Enable logging in config if you want future local event summaries; Mission Control does not mutate that setting.',
      tone: 'watch',
    });
  }

  if (stack.recent_events.include_full_transcripts) {
    items.push({
      label: 'Full transcript logging enabled',
      reason: 'Future local voice log events may include transcript bodies because explicit full transcript logging is on.',
      hint: 'Mission Control still hides full transcript text from status events and only shows sanitized summaries.',
      tone: 'watch',
    });
  }

  if (!items.length) {
    items.push({
      label: 'Setup troubleshooting',
      reason: 'No missing or unsafe setup items were detected in the current read-only status payload.',
      hint: 'Keep using explicit terminal commands for recording, dispatch, and speech; Mission Control does not execute them.',
      tone: 'good',
    });
  }

  return items;
}

function buildVoiceSafetyAuditSummary(
  status: VoicePttStatus | null,
  stack: VoiceStackStatus | undefined,
): VoiceSafetyAuditSummaryItem[] {
  const approvalRequired = stack?.approval.required ?? status?.requires_explicit_approval;
  const autoDispatchDisabled = typeof stack?.safety.auto_dispatch_enabled === 'boolean'
    ? !stack.safety.auto_dispatch_enabled
    : stack?.safety.dispatch_called === false;
  const autoSpeechDisabled = typeof stack?.safety.auto_speech_enabled === 'boolean'
    ? !stack.safety.auto_speech_enabled
    : stack?.safety.speech_called === false;
  const alwaysOnDisabled = stack ? stack.safety.always_on_listening === false : undefined;
  const hotkeyBridgeSafe = stack
    ? stack.hotkey_bridge.print_only
      && stack.hotkey_bridge.enabled === false
      && stack.hotkey_bridge.listener_started === false
      && stack.hotkey_bridge.global_key_capture === false
    : undefined;
  const rawAudioNotStored = stack
    ? stack.safety.raw_audio_stored === false && stack.recent_events.raw_audio_stored === false
    : undefined;
  const transcriptRedactionDefault = stack
    ? stack.recent_events.transcript_redaction_default ?? !stack.recent_events.include_full_transcripts
    : undefined;
  const fullTranscriptLogging = stack?.recent_events.include_full_transcripts;
  const localOnlyEventLogging = stack?.recent_events.local_only ?? stack?.recent_events.enabled;
  const counts = stack?.recent_events.counts;

  return [
    {
      label: 'Approval required',
      value: auditEnabledLabel(approvalRequired, 'Required', 'Not required'),
      detail: stack?.approval.config || 'Voice approval status pending',
      tone: approvalRequired ? 'good' : 'watch',
    },
    {
      label: 'Auto-dispatch',
      value: auditEnabledLabel(autoDispatchDisabled, 'Disabled', 'Enabled'),
      detail: 'Dispatch remains explicit after approval',
      tone: autoDispatchDisabled ? 'good' : 'watch',
    },
    {
      label: 'Auto-speech',
      value: auditEnabledLabel(autoSpeechDisabled, 'Disabled', 'Enabled'),
      detail: 'Speech output remains explicit',
      tone: autoSpeechDisabled ? 'good' : 'watch',
    },
    {
      label: 'Always-on listening',
      value: auditEnabledLabel(alwaysOnDisabled, 'Disabled', 'Enabled'),
      detail: status ? 'Push-to-talk/status flow only' : 'Voice status not loaded',
      tone: alwaysOnDisabled ? 'good' : 'watch',
    },
    {
      label: 'Hotkey bridge',
      value: auditEnabledLabel(hotkeyBridgeSafe, 'Disabled / print-only', 'Check required'),
      detail: stack?.hotkey_bridge.configured_format
        ? `Format: ${stack.hotkey_bridge.configured_format}`
        : 'Voice status not loaded',
      tone: hotkeyBridgeSafe ? 'good' : 'watch',
    },
    {
      label: 'Raw audio storage',
      value: auditEnabledLabel(rawAudioNotStored, 'Not stored', 'Stored'),
      detail: 'Status and event summaries do not expose raw audio',
      tone: rawAudioNotStored ? 'good' : 'watch',
    },
    {
      label: 'Transcript redaction',
      value: auditEnabledLabel(transcriptRedactionDefault, 'Default', 'Full text mode'),
      detail: transcriptRedactionDefault ? 'Length/hash/redacted preview by default' : 'Full transcript logging is enabled',
      tone: transcriptRedactionDefault ? 'good' : 'watch',
    },
    {
      label: 'Full transcript logging',
      value: enabledLabel(fullTranscriptLogging),
      detail: fullTranscriptLogging
        ? 'Only previously opted-in events may contain text'
        : 'Full transcript text hidden from status events',
      tone: fullTranscriptLogging ? 'watch' : 'good',
    },
    {
      label: 'Local-only event logging',
      value: enabledLabel(localOnlyEventLogging),
      detail: stack?.recent_events.enabled ? 'Configured JSONL event summaries' : 'Local event logging disabled',
      tone: localOnlyEventLogging ? 'quiet' : 'watch',
    },
    {
      label: 'Recent audit counts',
      value: counts ? `A ${counts.approval} / D ${counts.dispatch} / S ${counts.speech}` : 'Unavailable',
      detail: counts ? `From ${counts.total} recent safe events` : 'No safe event count data',
      tone: counts && counts.total > 0 ? 'quiet' : 'watch',
    },
  ];
}

function VoiceDiagnosticsSummary({ items }: { items: VoiceDiagnosticsSummaryItem[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const style = toneStyle(item.tone);
        return (
          <div
            key={item.label}
            className="min-w-0 rounded-md border px-3 py-2"
            style={{ borderColor: style.border, background: style.bg }}
          >
            <div className="text-[11px] font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              {item.label}
            </div>
            <div className="mt-1 truncate text-xs font-semibold" style={{ color: style.text }}>
              {item.value}
            </div>
            <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {item.detail}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VoiceReadinessSummary({ stack }: { stack: VoiceStackStatus | undefined }) {
  const readiness = stack?.readiness;
  const tone = voiceReadinessTone(readiness?.state);
  const style = toneStyle(tone);
  const blockers = readiness?.blocking_issues ?? [];
  const warnings = readiness?.warnings ?? [];
  const capabilities = [
    {
      label: 'Preview-only local pipeline',
      available: readiness?.preview_only_local_pipeline_available,
    },
    {
      label: 'Approval-gated dispatch',
      available: readiness?.approval_gated_dispatch_available,
    },
    {
      label: 'Optional speech output',
      available: readiness?.optional_speech_output_available,
    },
  ];

  return (
    <div
      className="grid gap-3 rounded-md border p-3 xl:grid-cols-[1.1fr_1fr]"
      style={{ borderColor: style.border, background: style.bg }}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={tone}>{voiceReadinessLabel(readiness?.state)}</StatusPill>
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            Read-only summary from voice status
          </span>
        </div>
        <div className="mt-3 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
          Blocking issues
        </div>
        {blockers.length ? (
          <ul className="mt-2 grid gap-1 text-xs leading-5" style={{ color: 'var(--color-text)' }}>
            {blockers.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        ) : (
          <div className="mt-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            No blocking issue reported.
          </div>
        )}
        <div className="mt-3 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
          Next safe manual step
        </div>
        <div className="mt-2 text-xs leading-5" style={{ color: 'var(--color-text)' }}>
          {readiness?.next_safe_manual_step || 'Load voice status before taking a manual setup step.'}
        </div>
      </div>

      <div className="grid gap-3">
        <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
          {capabilities.map((item) => (
            <div
              key={item.label}
              className="rounded-md border px-3 py-2"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg)',
              }}
            >
              <div className="text-[11px] font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
                {item.label}
              </div>
              <div className="mt-1 text-xs font-semibold" style={{ color: item.available ? 'var(--color-success)' : 'var(--color-warning)' }}>
                {yesNoLabel(item.available)}
              </div>
            </div>
          ))}
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
            Warnings
          </div>
          {warnings.length ? (
            <ul className="mt-2 grid gap-1 text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <div className="mt-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              No warning reported.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function VoiceSetupTroubleshooting({ items }: { items: VoiceSetupTroubleshootingItem[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const style = toneStyle(item.tone);
        return (
          <div
            key={item.label}
            className="min-w-0 rounded-md border px-3 py-3"
            style={{ borderColor: style.border, background: style.bg }}
          >
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 shrink-0" size={15} style={{ color: style.text }} />
              <div className="min-w-0">
                <div className="text-xs font-semibold" style={{ color: style.text }}>
                  {item.label}
                </div>
                <div className="mt-1 text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                  {item.reason}
                </div>
                <div className="mt-2 text-xs leading-5" style={{ color: 'var(--color-text)' }}>
                  {item.hint}
                </div>
                {item.manualReference ? (
                  <code
                    className="mt-2 block break-all rounded-md border px-2 py-1.5 text-[11px]"
                    style={{
                      borderColor: 'var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                    }}
                  >
                    {item.manualReference}
                  </code>
                ) : null}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VoiceSetupChecklist({ items }: { items: VoiceSetupChecklistItem[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
      {items.map((item) => {
        const style = toneStyle(item.tone);
        const Icon = item.tone === 'good' ? CheckCircle2 : item.tone === 'watch' ? AlertTriangle : Circle;
        return (
          <div
            key={item.label}
            className="min-w-0 rounded-md border px-3 py-2"
            style={{ borderColor: style.border, background: style.bg }}
          >
            <div className="flex items-start gap-2">
              <Icon className="mt-0.5 shrink-0" size={15} style={{ color: style.text }} />
              <div className="min-w-0">
                <div className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                  {item.label}
                </div>
                <div className="mt-1 text-xs font-semibold" style={{ color: style.text }}>
                  {item.value}
                </div>
                <div className="mt-1 truncate text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {item.detail}
                </div>
                {item.manualCommands?.length ? (
                  <div className="mt-3 grid gap-2">
                    <div className="text-[11px] font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
                      Manual terminal commands
                    </div>
                    {item.manualCommands.map((manualCommand) => (
                      <div
                        key={manualCommand.command}
                        className="rounded-md border px-2 py-2"
                        style={{
                          borderColor: 'var(--color-border)',
                          background: 'var(--color-bg)',
                        }}
                      >
                        <div className="flex items-start gap-2">
                          <code className="min-w-0 flex-1 break-all text-[11px]" style={{ color: 'var(--color-text)' }}>
                            {manualCommand.command}
                          </code>
                          <button
                            type="button"
                            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border"
                            style={{
                              borderColor: 'var(--color-border)',
                              color: 'var(--color-text-secondary)',
                              background: 'var(--color-bg-secondary)',
                            }}
                            title="Copy manual terminal command"
                            aria-label={`Copy manual terminal command: ${manualCommand.command}`}
                            onClick={() => copyManualCommand(manualCommand.command)}
                          >
                            <Clipboard size={13} />
                          </button>
                        </div>
                        <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                          {manualCommand.detail}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VoicePipelineCommandHelper({ commands }: { commands: VoiceManualCommand[] }) {
  return (
    <div className="grid gap-2 lg:grid-cols-3">
      {commands.map((manualCommand) => {
        const style = toneStyle(manualCommand.tone);
        return (
          <div
            key={manualCommand.label}
            className="min-w-0 rounded-md border px-3 py-3"
            style={{ borderColor: style.border, background: style.bg }}
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="text-xs font-semibold" style={{ color: style.text }}>
                {manualCommand.label}
              </div>
              <StatusPill tone={manualCommand.tone}>
                Manual terminal
              </StatusPill>
            </div>
            <div
              className="rounded-md border px-2 py-2"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg)',
              }}
            >
              <div className="flex items-start gap-2">
                <code className="min-w-0 flex-1 break-all text-[11px]" style={{ color: 'var(--color-text)' }}>
                  {manualCommand.command}
                </code>
                <button
                  type="button"
                  className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border"
                  style={{
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                    background: 'var(--color-bg-secondary)',
                  }}
                  title="Copy manual terminal command"
                  aria-label={`Copy manual terminal command: ${manualCommand.command}`}
                  onClick={() => copyManualCommand(manualCommand.command)}
                >
                  <Clipboard size={13} />
                </button>
              </div>
            </div>
            <div className="mt-2 text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>
              {manualCommand.detail}
            </div>
          </div>
        );
      })}
    </div>
  );
}

type RecentVoiceEvent = VoiceStackStatus['recent_events']['events'][number];
type RecentVoiceEventDetails = RecentVoiceEvent['details'];
type VoiceEventOutcomeFilter = 'all' | 'success' | 'failure';

type VoiceEventFilters = {
  eventType: string;
  status: string;
  outcome: VoiceEventOutcomeFilter;
  approvalDispatchOnly: boolean;
  search: string;
};

const defaultVoiceEventFilters: VoiceEventFilters = {
  eventType: 'all',
  status: 'all',
  outcome: 'all',
  approvalDispatchOnly: false,
  search: '',
};

const successVoiceStatuses = new Set(['ok', 'success', 'succeeded', 'complete', 'completed']);
const failureVoiceStatuses = new Set(['error', 'failed', 'failure']);

function eventTranscriptDetail(
  transcript: RecentVoiceEvent['transcript'],
): string {
  if (transcript.preview) return transcript.preview;
  if (transcript.full_transcript_logged) return 'Full transcript logged; panel shows redacted summaries only';
  if (typeof transcript.length === 'number' && transcript.length > 0) {
    return `Transcript length ${transcript.length}`;
  }
  return 'No transcript summary';
}

function voiceEventKey(event: RecentVoiceEvent, index: number): string {
  return `${event.timestamp}-${event.command}-${event.event}-${index}`;
}

function hasVoiceDetail(details: RecentVoiceEventDetails, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(details, key);
}

function formatVoiceDetail(value: RecentVoiceEventDetails[string] | undefined): string {
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'None';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (value === null || typeof value === 'undefined' || value === '') return 'Not recorded';
  return String(value);
}

function voiceDetailSummary(details: RecentVoiceEventDetails, keys: string[]): string {
  const parts = keys
    .filter((key) => hasVoiceDetail(details, key))
    .map((key) => `${key.replace(/_/g, ' ')}=${formatVoiceDetail(details[key])}`);
  return parts.length ? parts.join(' · ') : 'Not recorded';
}

function voiceActionSummary(details: RecentVoiceEventDetails, keys: string[]): string {
  const parts = keys
    .filter((key) => hasVoiceDetail(details, key))
    .map((key) => `${key.replace(/_/g, ' ')}=${formatVoiceDetail(details[key])}`);
  if (parts.length && hasVoiceDetail(details, 'reason')) {
    parts.push(`reason=${formatVoiceDetail(details.reason)}`);
  }
  return parts.length ? parts.join(' · ') : 'Not recorded';
}

function voiceApprovalSummary(details: RecentVoiceEventDetails): string {
  return voiceDetailSummary(details, ['approval_required', 'approved']);
}

function voiceDispatchSummary(details: RecentVoiceEventDetails): string {
  return voiceActionSummary(details, [
    'attempted',
    'dispatch_enabled',
    'dispatch_called',
    'dispatched',
    'dispatch_status',
    'agent_id',
  ]);
}

function voiceSpeechSummary(details: RecentVoiceEventDetails): string {
  return voiceActionSummary(details, [
    'speech_enabled',
    'speech_called',
    'spoken',
    'adapter',
    'speech_output',
  ]);
}

function voiceErrorSummary(event: RecentVoiceEvent): string {
  const details = event.details;
  const failedStatus = ['error', 'failed', 'failure'].includes(event.status);
  if (hasVoiceDetail(details, 'error_summary')) return formatVoiceDetail(details.error_summary);
  if (hasVoiceDetail(details, 'error')) return formatVoiceDetail(details.error);
  if (hasVoiceDetail(details, 'message')) return formatVoiceDetail(details.message);
  if (hasVoiceDetail(details, 'has_error')) {
    return details.has_error ? voiceDetailSummary(details, ['has_error', 'reason']) : 'No error recorded';
  }
  return failedStatus ? voiceDetailSummary(details, ['reason']) : 'No error recorded';
}

function voiceEventOutcome(event: RecentVoiceEvent): VoiceEventOutcomeFilter {
  const status = (event.status || '').toLowerCase();
  const hasExplicitError = Boolean(
    hasVoiceDetail(event.details, 'error_summary')
      || hasVoiceDetail(event.details, 'error')
      || event.details.has_error === true,
  );
  if (failureVoiceStatuses.has(status) || hasExplicitError) return 'failure';
  if (successVoiceStatuses.has(status)) return 'success';
  return 'all';
}

function isApprovalDispatchVoiceEvent(event: RecentVoiceEvent): boolean {
  const eventType = (event.event || '').toLowerCase();
  if (eventType.includes('approval') || eventType.includes('dispatch')) return true;
  return [
    'approval_required',
    'approved',
    'attempted',
    'dispatch_enabled',
    'dispatch_called',
    'dispatched',
    'dispatch_status',
  ].some((key) => hasVoiceDetail(event.details, key));
}

function voiceEventSearchText(event: RecentVoiceEvent): string {
  const transcript = event.transcript || {};
  return [
    event.command,
    event.event,
    event.status,
    event.timestamp,
    eventTranscriptDetail(transcript),
    typeof transcript.length === 'number' ? String(transcript.length) : '',
    transcript.sha256 || '',
    transcript.preview || '',
    voiceApprovalSummary(event.details),
    voiceDispatchSummary(event.details),
    voiceSpeechSummary(event.details),
    voiceErrorSummary(event),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

function filterVoiceEvents(
  events: RecentVoiceEvent[],
  filters: VoiceEventFilters,
): RecentVoiceEvent[] {
  const search = filters.search.trim().toLowerCase();
  return events.filter((event) => {
    if (filters.eventType !== 'all' && event.event !== filters.eventType) return false;
    if (filters.status !== 'all' && event.status !== filters.status) return false;
    if (filters.outcome !== 'all' && voiceEventOutcome(event) !== filters.outcome) return false;
    if (filters.approvalDispatchOnly && !isApprovalDispatchVoiceEvent(event)) return false;
    if (search && !voiceEventSearchText(event).includes(search)) return false;
    return true;
  });
}

function uniqueVoiceEventValues(
  events: RecentVoiceEvent[],
  getValue: (event: RecentVoiceEvent) => string,
): string[] {
  return Array.from(new Set(events.map(getValue).filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function VoiceEventDetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
        {label}
      </div>
      <div className="mt-1 break-words text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        {value}
      </div>
    </div>
  );
}

function VoiceEventDetails({ event }: { event: RecentVoiceEvent }) {
  const transcript = event.transcript || {};
  return (
    <div
      className="mt-3 grid gap-3 border-t pt-3 md:grid-cols-2 xl:grid-cols-3"
      style={{ borderColor: 'var(--color-border)' }}
    >
      <VoiceEventDetailRow label="Event type" value={event.event || 'Not recorded'} />
      <VoiceEventDetailRow label="Status" value={event.status || 'unknown'} />
      <VoiceEventDetailRow label="Timestamp" value={event.timestamp || 'Not recorded'} />
      <VoiceEventDetailRow
        label="Transcript length"
        value={typeof transcript.length === 'number' ? transcript.length : 'Not recorded'}
      />
      <VoiceEventDetailRow
        label="Transcript hash"
        value={transcript.sha256 ? <span className="break-all">{transcript.sha256}</span> : 'Not recorded'}
      />
      <VoiceEventDetailRow
        label="Redacted preview"
        value={transcript.preview || (transcript.full_transcript_logged ? 'Full transcript was logged; hidden in Mission Control' : 'Not recorded')}
      />
      <VoiceEventDetailRow label="Approval decision" value={voiceApprovalSummary(event.details)} />
      <VoiceEventDetailRow label="Dispatch" value={voiceDispatchSummary(event.details)} />
      <VoiceEventDetailRow label="Speech" value={voiceSpeechSummary(event.details)} />
      <VoiceEventDetailRow label="Error summary" value={voiceErrorSummary(event)} />
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
  const [preview, setPreview] = useState<VoiceSubmitTranscriptResponse | null>(null);
  const [dispatchResult, setDispatchResult] = useState<VoiceDispatchResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<'idle' | 'submitting' | 'dispatching' | 'cancelling'>('idle');
  const [fallbackFsmState, setFallbackFsmState] = useState('idle');
  const [expandedVoiceEventKey, setExpandedVoiceEventKey] = useState<string | null>(null);
  const [voiceEventFilters, setVoiceEventFilters] = useState<VoiceEventFilters>(defaultVoiceEventFilters);

  const loadVoiceStatus = async () => {
    try {
      const data = await fetchVoicePttStatus();
      setStatus(data);
      setFallbackFsmState(data.fsm_state || 'idle');
      setError('');
    } catch {
      setStatus(null);
    }
  };

  useEffect(() => {
    loadVoiceStatus();
  }, []);

  const fsmState = status?.fsm_state || fallbackFsmState;

  const updateFsmState = (fsmState: string) => {
    setFallbackFsmState(fsmState);
    setStatus((current) => (current ? { ...current, fsm_state: fsmState } : current));
  };

  const submitMockTranscript = async () => {
    if (busy !== 'idle' || fsmState !== 'idle' || !transcript.trim()) return;
    setBusy('submitting');
    setPreview(null);
    setDispatchResult(null);
    setError('');
    try {
      const response = await submitVoiceTranscript(transcript.trim());
      setPreview(response);
      updateFsmState(response.fsm_state);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcript preview failed');
    } finally {
      setBusy('idle');
    }
  };

  const approveAndDispatch = async () => {
    if (busy !== 'idle' || fsmState !== 'awaiting_approval' || !preview?.transcript.trim()) return;
    setBusy('dispatching');
    setError('');
    try {
      updateFsmState('dispatching');
      const response = await dispatchVoiceTranscript(preview.transcript, status?.active_agent_id || '');
      setDispatchResult(response);
      updateFsmState(response.fsm_state);
      if (!response.dispatched) {
        setError(response.error?.message || response.reason || 'Voice dispatch was not completed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Voice dispatch failed');
    } finally {
      setBusy('idle');
    }
  };

  const cancelMockTranscript = async () => {
    if (busy !== 'idle') return;
    setBusy('cancelling');
    setError('');
    try {
      const response = await cancelVoiceSession();
      setPreview(null);
      setDispatchResult(null);
      updateFsmState(response.fsm_state);
      await loadVoiceStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Voice cancel failed');
    } finally {
      setBusy('idle');
    }
  };

  const recording = status?.recording ?? false;
  const latest = status?.latest;
  const stack = status?.voice_stack;
  const voiceSetupChecklist = useMemo(
    () => buildVoiceSetupChecklist(status, stack),
    [status, stack],
  );
  const voiceDiagnosticsSummary = useMemo(
    () => buildVoiceDiagnosticsSummary(status, stack),
    [status, stack],
  );
  const voiceSafetyAuditSummary = useMemo(
    () => buildVoiceSafetyAuditSummary(status, stack),
    [status, stack],
  );
  const voiceSetupTroubleshooting = useMemo(
    () => buildVoiceSetupTroubleshooting(status, stack),
    [status, stack],
  );
  const voicePipelineManualCommands = useMemo(
    () => buildVoicePipelineManualCommands(stack),
    [stack],
  );
  const recentVoiceEvents = stack?.recent_events.events ?? [];
  const voiceEventTypeOptions = useMemo(
    () => uniqueVoiceEventValues(recentVoiceEvents, (event) => event.event),
    [recentVoiceEvents],
  );
  const voiceEventStatusOptions = useMemo(
    () => uniqueVoiceEventValues(recentVoiceEvents, (event) => event.status),
    [recentVoiceEvents],
  );
  const filteredVoiceEvents = useMemo(
    () => filterVoiceEvents(recentVoiceEvents, voiceEventFilters),
    [recentVoiceEvents, voiceEventFilters],
  );
  const hasVoiceEventFilters = voiceEventFilters.eventType !== defaultVoiceEventFilters.eventType
    || voiceEventFilters.status !== defaultVoiceEventFilters.status
    || voiceEventFilters.outcome !== defaultVoiceEventFilters.outcome
    || voiceEventFilters.approvalDispatchOnly !== defaultVoiceEventFilters.approvalDispatchOnly
    || voiceEventFilters.search.trim().length > 0;
  const intent = preview?.intent_preview || latest?.intent_preview;
  const canSubmit = busy === 'idle' && fsmState === 'idle' && transcript.trim().length > 0;
  const canApprove = busy === 'idle' && fsmState === 'awaiting_approval' && Boolean(preview?.transcript.trim());
  const canCancel = busy === 'idle' && fsmState !== 'idle';
  const textDisabled = fsmState !== 'idle' || busy !== 'idle';
  const buttonLabel = 'PTT deferred';
  const stateLabel = busy === 'submitting'
    ? 'Previewing'
    : busy === 'dispatching'
      ? 'Dispatching'
      : busy === 'cancelling'
        ? 'Cancelling'
        : fsmState.replace(/_/g, ' ');
  const displayedTranscript = preview?.transcript || transcript || '';
  const completionDetail = dispatchResult?.dispatched
    ? `Dispatched${dispatchResult.agent_id ? ` to ${dispatchResult.agent_id}` : ''}`
    : dispatchResult?.reason || dispatchResult?.error?.message || 'No dispatch yet';
  const updateVoiceEventFilter = <K extends keyof VoiceEventFilters>(
    key: K,
    value: VoiceEventFilters[K],
  ) => {
    setVoiceEventFilters((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="grid gap-4">
      <ShellPanel title="Voice Control Status" action="read only">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <ContextTile
            icon={<Mic2 size={15} />}
            label="FSM"
            value={stateLabel}
            detail={status?.push_to_talk_only ? 'Push-to-talk only' : 'Voice status pending'}
          />
          <ContextTile
            icon={<Radar size={15} />}
            label="API Base"
            value={stack?.api_base_url.value || 'Unknown'}
            detail={stack?.api_base_url.source || 'Voice status pending'}
          />
          <ContextTile
            icon={<Cpu size={15} />}
            label="Transcription"
            value={configuredVoiceValue(stack?.transcription_adapter.configured)}
            detail={`Effective: ${stack?.transcription_adapter.effective || 'unknown'}`}
          />
          <ContextTile
            icon={<Package size={15} />}
            label="Model Path"
            value={modelPathStatus(stack?.model_path)}
            detail={stack?.model_path.value ? compactPath(stack.model_path.value) : 'No model path configured'}
          />
          <ContextTile
            icon={<Clock3 size={15} />}
            label="Default Duration"
            value={formatVoiceDuration(stack?.record_duration.effective_default_seconds)}
            detail={stack?.record_duration.duration_flag_required ? 'CLI flag required' : 'Configured default'}
          />
          <ContextTile
            icon={<Activity size={15} />}
            label="Speech Output"
            value={stack?.speech_output.backend || 'Unknown'}
            detail={configuredVoiceValue(stack?.speech_output.configured, 'Default adapter')}
          />
          <ContextTile
            icon={<TerminalSquare size={15} />}
            label="macOS Say"
            value={stack ? (stack.macos_say.available ? 'Available' : 'Unavailable') : 'Unknown'}
            detail={stack?.macos_say.relevant ? 'Relevant backend' : 'Not selected'}
          />
          <ContextTile
            icon={<Ban size={15} />}
            label="Hotkey Bridge"
            value={stack?.hotkey_bridge.enabled ? 'Enabled' : 'Disabled'}
            detail={stack?.hotkey_bridge.print_only ? 'Print-only preview' : 'No listener started'}
          />
          <ContextTile
            icon={<ShieldCheck size={15} />}
            label="Approval"
            value={(stack?.approval.required ?? status?.requires_explicit_approval) ? 'Required' : 'Not required'}
            detail="No approval bypass"
          />
          <ContextTile
            icon={<LockKeyhole size={15} />}
            label="Safety"
            value={stack?.safety.always_on_listening ? 'Listening' : 'Passive'}
            detail="No auto dispatch or speech"
          />
        </div>

        <div className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Voice readiness summary
            </h3>
            <StatusPill tone={voiceReadinessTone(stack?.readiness.state)}>
              {voiceReadinessLabel(stack?.readiness.state)}
            </StatusPill>
          </div>
          <VoiceReadinessSummary stack={stack} />
        </div>

        <div className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Voice diagnostics summary
            </h3>
            <StatusPill tone="quiet">Read only</StatusPill>
          </div>
          <VoiceDiagnosticsSummary items={voiceDiagnosticsSummary} />
        </div>

        <div className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Voice safety audit summary
            </h3>
            <StatusPill tone="quiet">Read only</StatusPill>
          </div>
          <VoiceDiagnosticsSummary items={voiceSafetyAuditSummary} />
        </div>

        <div className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Local pipeline command helper
            </h3>
            <StatusPill tone="quiet">Copy only</StatusPill>
          </div>
          <VoicePipelineCommandHelper commands={voicePipelineManualCommands} />
        </div>

        <div className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Voice setup checklist
            </h3>
            <StatusPill tone="quiet">Read only</StatusPill>
          </div>
          <VoiceSetupChecklist items={voiceSetupChecklist} />
        </div>

        <div className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Voice setup troubleshooting
            </h3>
            <StatusPill tone="quiet">Read only</StatusPill>
          </div>
          <VoiceSetupTroubleshooting items={voiceSetupTroubleshooting} />
        </div>

        <div className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-tertiary)' }}>
              Recent redacted voice events
            </h3>
            <StatusPill tone={stack?.recent_events.enabled ? 'quiet' : 'watch'}>
              {stack?.recent_events.enabled
                ? `${filteredVoiceEvents.length}/${recentVoiceEvents.length} shown`
                : 'Logs unavailable'}
            </StatusPill>
          </div>
          {recentVoiceEvents.length ? (
            <div
              className="mb-3 grid gap-2 rounded-md border p-3 lg:grid-cols-[1fr_1fr_1fr_auto] xl:grid-cols-[1fr_1fr_1fr_auto_1.4fr_auto]"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
              }}
            >
              <label className="grid gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <span className="font-medium">Event type</span>
                <select
                  value={voiceEventFilters.eventType}
                  onChange={(event) => updateVoiceEventFilter('eventType', event.target.value)}
                  className="h-9 rounded-md border px-2 text-xs"
                  style={{
                    borderColor: 'var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text)',
                  }}
                >
                  <option value="all">All event types</option>
                  {voiceEventTypeOptions.map((eventType) => (
                    <option key={eventType} value={eventType}>{eventType}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <span className="font-medium">Status</span>
                <select
                  value={voiceEventFilters.status}
                  onChange={(event) => updateVoiceEventFilter('status', event.target.value)}
                  className="h-9 rounded-md border px-2 text-xs"
                  style={{
                    borderColor: 'var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text)',
                  }}
                >
                  <option value="all">All statuses</option>
                  {voiceEventStatusOptions.map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <span className="font-medium">Outcome</span>
                <select
                  value={voiceEventFilters.outcome}
                  onChange={(event) => updateVoiceEventFilter('outcome', event.target.value as VoiceEventOutcomeFilter)}
                  className="h-9 rounded-md border px-2 text-xs"
                  style={{
                    borderColor: 'var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text)',
                  }}
                >
                  <option value="all">Success and failure</option>
                  <option value="success">Success only</option>
                  <option value="failure">Failure only</option>
                </select>
              </label>
              <label
                className="flex min-h-9 items-center gap-2 self-end rounded-md border px-3 text-xs"
                style={{
                  borderColor: 'var(--color-border)',
                  background: 'var(--color-bg)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                <input
                  type="checkbox"
                  checked={voiceEventFilters.approvalDispatchOnly}
                  onChange={(event) => updateVoiceEventFilter('approvalDispatchOnly', event.target.checked)}
                />
                <span>Approval/dispatch only</span>
              </label>
              <label className="grid gap-1 text-xs lg:col-span-3 xl:col-span-1" style={{ color: 'var(--color-text-secondary)' }}>
                <span className="font-medium">Search displayed fields</span>
                <span
                  className="flex h-9 items-center gap-2 rounded-md border px-2"
                  style={{
                    borderColor: 'var(--color-border)',
                    background: 'var(--color-bg)',
                  }}
                >
                  <Search size={14} style={{ color: 'var(--color-text-tertiary)' }} />
                  <input
                    value={voiceEventFilters.search}
                    onChange={(event) => updateVoiceEventFilter('search', event.target.value)}
                    placeholder="Search redacted event text"
                    className="min-w-0 flex-1 bg-transparent text-xs outline-none"
                    style={{ color: 'var(--color-text)' }}
                  />
                </span>
              </label>
              <button
                type="button"
                disabled={!hasVoiceEventFilters}
                className="inline-flex h-9 items-center justify-center gap-2 self-end rounded-md border px-3 text-xs font-medium disabled:opacity-50"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-secondary)',
                  background: 'var(--color-bg)',
                }}
                onClick={() => setVoiceEventFilters(defaultVoiceEventFilters)}
              >
                <XCircle size={14} />
                Reset filters
              </button>
            </div>
          ) : null}
          {recentVoiceEvents.length ? (
            filteredVoiceEvents.length ? (
              <div className="grid gap-2">
                {filteredVoiceEvents.map((event, index) => {
                const key = voiceEventKey(event, index);
                const expanded = expandedVoiceEventKey === key;
                return (
                  <div
                    key={key}
                    className="rounded-md border px-3 py-2"
                    style={{
                      borderColor: 'var(--color-border)',
                      background: 'var(--color-bg-secondary)',
                    }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <span className="font-medium" style={{ color: 'var(--color-text)' }}>
                        {event.command || 'voice'} / {event.event || 'event'}
                      </span>
                      <div className="flex items-center gap-2">
                        <span style={{ color: 'var(--color-text-tertiary)' }}>
                          {formatTime(event.timestamp)}
                        </span>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs"
                          style={{
                            borderColor: 'var(--color-border)',
                            color: 'var(--color-text-secondary)',
                            background: 'var(--color-bg)',
                          }}
                          aria-expanded={expanded}
                          aria-label={expanded ? 'Hide voice event details' : 'Inspect voice event details'}
                          onClick={() => setExpandedVoiceEventKey(expanded ? null : key)}
                        >
                          <Eye size={13} />
                          {expanded ? 'Hide' : 'Inspect'}
                        </button>
                      </div>
                    </div>
                    <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      status={event.status || 'unknown'} · {eventTranscriptDetail(event.transcript)}
                    </div>
                    {expanded && <VoiceEventDetails event={event} />}
                  </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
                No local voice events match the current filters.
              </p>
            )
          ) : (
            <p className="text-sm" style={{ color: 'var(--color-text-tertiary)' }}>
              No local voice events available.
            </p>
          )}
        </div>
      </ShellPanel>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <ShellPanel title="Voice Push-to-Talk" action="mock transcript">
        <div className="grid gap-3 md:grid-cols-3">
          <ContextTile
            icon={<Mic2 size={15} />}
            label="FSM"
            value={stateLabel}
            detail="Typed mock transcript only"
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
            disabled
            className="inline-flex h-12 min-w-40 items-center justify-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors disabled:opacity-60"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
              background: 'var(--color-bg-secondary)',
            }}
            title="Live microphone recording is deferred"
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
            {recording ? 'Live capture' : status?.privacy_mode ? 'Privacy gate' : 'Mock flow'}
          </StatusPill>
          <StatusPill tone={fsmState === 'awaiting_approval' ? 'watch' : dispatchResult?.dispatched ? 'good' : 'quiet'}>
            {fsmState === 'awaiting_approval' ? 'Awaiting approval' : dispatchResult?.dispatched ? 'Completed' : 'Typed only'}
          </StatusPill>
        </div>

        <div className="mt-5 grid gap-3">
          <label className="grid gap-2 text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            Mock transcript
            <textarea
              value={transcript}
              onChange={(event) => setTranscript(event.target.value)}
              disabled={textDisabled}
              rows={5}
              className="min-h-28 resize-none rounded-md border px-3 py-3 text-sm font-normal leading-6 outline-none transition-colors disabled:opacity-60"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
                color: 'var(--color-text)',
              }}
              placeholder="Type the transcript to preview. No microphone, local recorder, or transcription runs in Phase 3."
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={submitMockTranscript}
              disabled={!canSubmit}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-50"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
                color: 'var(--color-text)',
              }}
            >
              <Search size={15} />
              Preview
            </button>
            {fsmState === 'awaiting_approval' && (
              <button
                type="button"
                onClick={approveAndDispatch}
                disabled={!canApprove}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-50"
                style={{
                  borderColor: 'var(--color-border)',
                  background: 'var(--color-accent)',
                  color: 'white',
                }}
              >
                <CheckCircle2 size={15} />
                Approve & Dispatch
              </button>
            )}
            <button
              type="button"
              onClick={cancelMockTranscript}
              disabled={!canCancel}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors disabled:opacity-50"
              style={{
                borderColor: 'var(--color-border)',
                background: 'var(--color-bg-secondary)',
                color: 'var(--color-text-secondary)',
              }}
            >
              <XCircle size={15} />
              Cancel
            </button>
          </div>
        </div>

        {error && (
          <p className="mt-4 text-sm" style={{ color: 'var(--color-error)' }}>
            {error}
          </p>
        )}
      </ShellPanel>

      <ShellPanel title="Transcript Preview" action={fsmState === 'awaiting_approval' ? 'approval required' : 'not sent'}>
        <div
          className="min-h-40 rounded-md border p-4 text-sm leading-6"
          style={{
            borderColor: 'var(--color-border)',
            background: 'var(--color-bg-secondary)',
            color: displayedTranscript ? 'var(--color-text)' : 'var(--color-text-tertiary)',
          }}
        >
          {displayedTranscript || 'No mock transcript preview yet'}
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <ContextTile
            icon={<Clock3 size={15} />}
            label="Phase"
            value="Phase 3"
            detail="Typed/mock only"
          />
          <ContextTile
            icon={<Package size={15} />}
            label="Recording"
            value="Deferred"
            detail="No raw audio"
          />
          <ContextTile
            icon={<Activity size={15} />}
            label="Dispatch"
            value={dispatchResult?.status || 'Pending'}
            detail={completionDetail}
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

// ---------------------------------------------------------------------------
// Knowledge Vault Section
// ---------------------------------------------------------------------------

function NoteTypeBadge({ type }: { type: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    daily: { bg: 'color-mix(in srgb, var(--color-accent) 15%, transparent)', text: 'var(--color-accent)' },
    project: { bg: 'color-mix(in srgb, var(--color-success) 15%, transparent)', text: 'var(--color-success)' },
    research: { bg: 'color-mix(in srgb, var(--color-warning) 15%, transparent)', text: 'var(--color-warning)' },
    note: { bg: 'var(--color-bg-secondary)', text: 'var(--color-text-secondary)' },
  };
  const c = colors[type] || colors.note;
  return (
    <span
      className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium"
      style={{ background: c.bg, color: c.text }}
    >
      {type}
    </span>
  );
}

type BrainGraphNodeKind = 'root' | 'center' | 'connected' | 'timeline' | 'search';

interface BrainGraphVisualNode {
  id: string;
  title: string;
  subtitle: string;
  kind: BrainGraphNodeKind;
  x: number;
  y: number;
  size: number;
  node?: KnowledgeGraphNode;
  event?: KnowledgeTimelineEvent;
  pinnedRoot?: boolean;
}

interface BrainGraphVisualEdge {
  id: string;
  sourceId: string;
  targetId: string;
  relationship: string;
  strength: number;
}

const compactGraphLabel = (value: string, max = 22) => (
  value.length > max ? `${value.slice(0, max - 1)}…` : value
);

const graphNodeTone = (kind: BrainGraphNodeKind, nodeType?: string) => {
  if (kind === 'center') {
    return {
      fill: 'color-mix(in srgb, var(--color-accent) 20%, var(--color-bg-secondary))',
      stroke: 'var(--color-accent)',
      text: 'var(--color-text)',
    };
  }
  if (kind === 'root') {
    return {
      fill: 'color-mix(in srgb, var(--color-success) 16%, var(--color-bg-secondary))',
      stroke: 'var(--color-success)',
      text: 'var(--color-text)',
    };
  }
  if (kind === 'timeline') {
    return {
      fill: 'color-mix(in srgb, var(--color-warning) 16%, var(--color-bg-secondary))',
      stroke: 'var(--color-warning)',
      text: 'var(--color-text)',
    };
  }
  if (kind === 'search') {
    return {
      fill: 'color-mix(in srgb, var(--color-accent) 10%, var(--color-bg-secondary))',
      stroke: 'color-mix(in srgb, var(--color-accent) 55%, var(--color-border))',
      text: 'var(--color-text)',
    };
  }
  if (nodeType === 'memory') {
    return {
      fill: 'color-mix(in srgb, var(--color-accent) 14%, var(--color-bg-secondary))',
      stroke: 'color-mix(in srgb, var(--color-accent) 70%, var(--color-border))',
      text: 'var(--color-text)',
    };
  }
  return {
    fill: 'var(--color-bg-secondary)',
    stroke: 'var(--color-border)',
    text: 'var(--color-text)',
  };
};

const relationLabel = (value: string) => value.replace(/_/g, ' ');

function KnowledgeVaultSection() {
  const [notes, setNotes] = useState<KnowledgeNoteListItem[]>([]);
  const [tags, setTags] = useState<VaultTag[]>([]);
  const [dailyNote, setDailyNote] = useState<KnowledgeNote | null>(null);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<KnowledgeNoteListItem[] | null>(null);
  const [live, setLive] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newType, setNewType] = useState<'note' | 'project' | 'research'>('note');
  const [brainFirstMode, setBrainFirstMode] = useState(false);
  const [graphStatus, setGraphStatus] = useState<KnowledgeGraphStatus | null>(null);
  const [graphRoots, setGraphRoots] = useState<KnowledgeGraphNode[]>([]);
  const [timeline, setTimeline] = useState<KnowledgeTimelineEvent[]>([]);
  const [neighborhoodQuery, setNeighborhoodQuery] = useState('');
  const [neighborhoodResults, setNeighborhoodResults] = useState<KnowledgeNeighborhoodSearchResult[]>([]);
  const [selectedGraphNode, setSelectedGraphNode] = useState<KnowledgeGraphNode | null>(null);
  const [hoveredGraphNodeId, setHoveredGraphNodeId] = useState<string | null>(null);
  const [graphNeighborhood, setGraphNeighborhood] = useState<KnowledgeGraphNeighborhood | null>(null);
  const [graphLoadingNodeId, setGraphLoadingNodeId] = useState<string | null>(null);
  const [connectedNodes, setConnectedNodes] = useState<KnowledgeGraphNode[]>([]);
  const [connectedEdges, setConnectedEdges] = useState(0);

  const load = async () => {
    try {
      const [noteList, tagList, daily, status, roots, events] = await Promise.all([
        fetchKnowledgeNotes({ limit: 40 }),
        fetchVaultTags(),
        getDailyNote().catch(() => null),
        fetchKnowledgeGraphStatus().catch(() => null),
        fetchGraphRoots(8).catch(() => []),
        fetchKnowledgeTimeline(8).catch(() => []),
      ]);
      setNotes(noteList);
      setTags(tagList);
      setDailyNote(daily);
      setGraphStatus(status);
      setGraphRoots(roots);
      setTimeline(events);
      setLive(true);
    } catch {
      setLive(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSearch = async (q: string) => {
    setSearchQuery(q);
    if (!q.trim()) { setSearchResults(null); return; }
    try {
      const results = await searchKnowledgeVault(q, 20);
      setSearchResults(results);
    } catch {
      setSearchResults([]);
    }
  };

  const handleTagFilter = async (tag: string | null) => {
    setSelectedTag(tag);
    setSearchResults(null);
    setSearchQuery('');
    if (!tag) { await load(); return; }
    try {
      const filtered = await fetchKnowledgeNotes({ tag, limit: 40 });
      setNotes(filtered);
    } catch {}
  };

  const handlePin = async (note: KnowledgeNoteListItem) => {
    try {
      await pinKnowledgeNote(note.id, !note.pinned);
      await load();
    } catch {}
  };

  const handleDelete = async (noteId: string) => {
    try {
      await deleteKnowledgeNote(noteId);
      await load();
    } catch {}
  };

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      await createKnowledgeNote({ title: newTitle.trim(), note_type: newType });
      setNewTitle('');
      setCreating(false);
      await load();
    } catch {
      setCreating(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportResult(null);
    try {
      const result = await exportVault();
      setExportResult(`Exported ${result.exported_count} notes → ${result.output_directory}`);
    } catch (e: any) {
      setExportResult(`Export failed: ${e.message}`);
    } finally {
      setExporting(false);
    }
  };

  const handleNeighborhoodSearch = async (q: string) => {
    setNeighborhoodQuery(q);
    if (!q.trim()) { setNeighborhoodResults([]); return; }
    try {
      const results = await searchKnowledgeNeighborhood(q, { limit: 8, max_depth: 2 });
      setNeighborhoodResults(results);
    } catch {
      setNeighborhoodResults([]);
    }
  };

  const handleGraphNodeSelect = async (node: KnowledgeGraphNode) => {
    setSelectedGraphNode(node);
    setGraphLoadingNodeId(node.id);
    try {
      const graph = await fetchGraphTraversal(node.id, { max_depth: 2 });
      setGraphNeighborhood(graph);
      setConnectedNodes(graph.nodes.filter((item) => item.id !== node.id).slice(0, 8));
      setConnectedEdges(graph.edges.length);
    } catch {
      setGraphNeighborhood(null);
      setConnectedNodes([]);
      setConnectedEdges(0);
    } finally {
      setGraphLoadingNodeId(null);
    }
  };

  useEffect(() => {
    if (!selectedGraphNode && graphRoots.length > 0) {
      void handleGraphNodeSelect(graphRoots[0]);
    }
  }, [graphRoots, selectedGraphNode]);

  const visibleNotes = searchResults ?? notes;
  const brainGraph = useMemo(() => {
    const visualNodes: BrainGraphVisualNode[] = [];
    const visualEdges: BrainGraphVisualEdge[] = [];
    const seen = new Set<string>();
    const rootIds = new Set(graphRoots.map((node) => node.id));
    const selectedId = selectedGraphNode?.id ?? null;
    const connected = graphNeighborhood?.nodes.filter((node) => node.id !== selectedId) ?? [];
    const searched = neighborhoodResults.map((result) => result.node);

    const addGraphNode = (
      node: KnowledgeGraphNode,
      kind: BrainGraphNodeKind,
      x: number,
      y: number,
      size: number,
    ) => {
      if (seen.has(node.id)) return;
      seen.add(node.id);
      visualNodes.push({
        id: node.id,
        title: node.title,
        subtitle: node.source || node.node_type,
        kind,
        x,
        y,
        size,
        node,
        pinnedRoot: node.pinned_root,
      });
    };

    if (selectedGraphNode) {
      addGraphNode(selectedGraphNode, 'center', 382, 180, 50);
    }

    graphRoots.slice(0, 5).forEach((node, index) => {
      if (node.id === selectedId) return;
      const positions = [
        [180, 82],
        [106, 176],
        [198, 274],
        [278, 142],
        [292, 246],
      ];
      const [x, y] = positions[index] ?? [150 + index * 36, 110 + index * 42];
      addGraphNode(node, 'root', x, y, node.pinned_root ? 43 : 36);
    });

    const connectedNodes = (connected.length > 0 ? connected : searched)
      .filter((node) => node.id !== selectedId && !rootIds.has(node.id))
      .slice(0, 8);
    connectedNodes.forEach((node, index) => {
      const angle = (-95 + index * (190 / Math.max(connectedNodes.length - 1, 1))) * (Math.PI / 180);
      addGraphNode(
        node,
        connected.length > 0 ? 'connected' : 'search',
        492 + Math.cos(angle) * 145,
        180 + Math.sin(angle) * 124,
        node.node_type === 'memory' ? 34 : 30,
      );
    });

    timeline.slice(0, 5).forEach((event, index) => {
      const timelineId = `timeline-${event.id}`;
      visualNodes.push({
        id: timelineId,
        title: event.title,
        subtitle: event.event_type,
        kind: 'timeline',
        x: 340 + index * 78,
        y: 332,
        size: 24,
        event,
      });
      if (event.node_id && seen.has(event.node_id)) {
        visualEdges.push({
          id: `${timelineId}-${event.node_id}`,
          sourceId: timelineId,
          targetId: event.node_id,
          relationship: event.event_type,
          strength: 0.45,
        });
      }
    });

    const edgeSource = graphNeighborhood?.edges.length
      ? graphNeighborhood.edges
      : neighborhoodResults.flatMap((result) => result.edges);
    edgeSource.slice(0, 16).forEach((edge: KnowledgeGraphEdge) => {
      if (!seen.has(edge.source_id) || !seen.has(edge.target_id)) return;
      visualEdges.push({
        id: edge.id,
        sourceId: edge.source_id,
        targetId: edge.target_id,
        relationship: edge.relationship,
        strength: edge.weight,
      });
    });

    if (selectedGraphNode) {
      connectedNodes.forEach((node) => {
        const hasVisibleEdge = visualEdges.some((edge) => (
          (edge.sourceId === selectedGraphNode.id && edge.targetId === node.id)
          || (edge.sourceId === node.id && edge.targetId === selectedGraphNode.id)
        ));
        if (!hasVisibleEdge) {
          visualEdges.push({
            id: `${selectedGraphNode.id}-${node.id}`,
            sourceId: selectedGraphNode.id,
            targetId: node.id,
            relationship: 'related',
            strength: 0.35,
          });
        }
      });
    }

    return { nodes: visualNodes, edges: visualEdges };
  }, [graphNeighborhood, graphRoots, neighborhoodResults, selectedGraphNode, timeline]);

  const graphNodeById = useMemo(() => {
    const lookup = new Map<string, BrainGraphVisualNode>();
    brainGraph.nodes.forEach((node) => lookup.set(node.id, node));
    return lookup;
  }, [brainGraph.nodes]);
  const graphDataNodeById = useMemo(() => {
    const lookup = new Map<string, KnowledgeGraphNode>();
    graphRoots.forEach((node) => lookup.set(node.id, node));
    graphNeighborhood?.nodes.forEach((node) => lookup.set(node.id, node));
    neighborhoodResults.forEach((result) => lookup.set(result.node.id, result.node));
    if (selectedGraphNode) lookup.set(selectedGraphNode.id, selectedGraphNode);
    return lookup;
  }, [graphNeighborhood, graphRoots, neighborhoodResults, selectedGraphNode]);
  const relationshipSummary = (graphNeighborhood?.edges.length
    ? graphNeighborhood.edges
    : neighborhoodResults.flatMap((result) => result.edges)
  ).slice(0, 5);
  const relationshipDetails = relationshipSummary.map((edge) => ({
    edge,
    source: graphDataNodeById.get(edge.source_id)?.title || graphNodeById.get(edge.source_id)?.title || 'Source node',
    target: graphDataNodeById.get(edge.target_id)?.title || graphNodeById.get(edge.target_id)?.title || 'Target node',
    timelineContext: timeline.find((event) => (
      event.node_id === edge.source_id || event.node_id === edge.target_id
    )),
  }));
  const timelineNodeIds = new Set(timeline.map((event) => event.node_id).filter(Boolean));
  const timelineRelevantNodes = brainGraph.nodes.filter((node) => node.node && timelineNodeIds.has(node.node.id)).slice(0, 4);
  const activeBrainNode = hoveredGraphNodeId
    ? graphNodeById.get(hoveredGraphNodeId)
    : selectedGraphNode
      ? graphNodeById.get(selectedGraphNode.id)
      : null;
  const activeGraphNode = activeBrainNode?.node ?? selectedGraphNode;
  const activeTimelineEvent = activeBrainNode?.event ?? timeline.find((event) => event.node_id === activeGraphNode?.id);
  const activeGraphLinks = activeGraphNode
    ? (graphNeighborhood?.edges ?? []).filter((edge) => (
      edge.source_id === activeGraphNode.id || edge.target_id === activeGraphNode.id
    ))
    : [];

  return (
    <div className={brainFirstMode ? 'grid gap-4' : 'grid gap-4 xl:grid-cols-[1fr_280px]'}>
      {/* Main panel */}
      <div className="grid gap-4">
        {/* Header row */}
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-4"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)', order: 1 }}
        >
          <div className="flex items-center gap-3">
            <BookMarked size={20} style={{ color: 'var(--color-accent)' }} />
            <div>
              <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                Knowledge Vault
              </div>
              <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                {live ? `${notes.length} notes · local only` : 'Waiting for backend…'}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              id="brain-first-mode-toggle"
              type="button"
              onClick={() => setBrainFirstMode((value) => !value)}
              className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-medium"
              style={{
                borderColor: brainFirstMode ? 'var(--color-accent)' : 'var(--color-border)',
                color: brainFirstMode ? 'var(--color-accent)' : 'var(--color-text)',
                background: brainFirstMode ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
              }}
            >
              <Brain size={14} />
              {brainFirstMode ? 'Brain First' : 'Focus Brain'}
            </button>
            <button
              id="vault-export-btn"
              type="button"
              disabled={exporting}
              onClick={handleExport}
              className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-medium disabled:opacity-50"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)', background: 'var(--color-bg-secondary)' }}
            >
              <FileDown size={14} />
              {exporting ? 'Exporting…' : 'Export Vault'}
            </button>
          </div>
        </div>

        {exportResult && (
          <div
            className="rounded-md border px-4 py-3 text-xs"
            style={{
              borderColor: exportResult.startsWith('Export failed') ? 'color-mix(in srgb, var(--color-warning) 40%, transparent)' : 'color-mix(in srgb, var(--color-success) 40%, transparent)',
              color: exportResult.startsWith('Export failed') ? 'var(--color-warning)' : 'var(--color-success)',
              background: 'var(--color-bg-secondary)',
            }}
          >
            {exportResult}
          </div>
        )}

        {/* Create note */}
        <details
          open={!brainFirstMode}
          className="hud-panel p-4"
          style={{ order: 3 }}
        >
          <summary className="cursor-pointer list-none text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            New Note
          </summary>
          <div className="mt-4 flex flex-wrap gap-2">
            <input
              id="vault-new-title"
              type="text"
              placeholder="Note title…"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); }}
              className="h-9 flex-1 rounded-md border bg-transparent px-3 text-sm outline-none"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            />
            <select
              id="vault-new-type"
              value={newType}
              onChange={(e) => setNewType(e.target.value as 'note' | 'project' | 'research')}
              className="h-9 rounded-md border bg-transparent px-2 text-sm"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)', background: 'var(--color-bg-secondary)' }}
            >
              <option value="note">note</option>
              <option value="project">project</option>
              <option value="research">research</option>
            </select>
            <button
              id="vault-create-btn"
              type="button"
              disabled={creating || !newTitle.trim()}
              onClick={handleCreate}
              className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-medium disabled:opacity-50"
              style={{ borderColor: 'var(--color-accent)', color: 'var(--color-accent)', background: 'var(--color-accent-subtle)' }}
            >
              <Plus size={14} />
              {creating ? 'Creating…' : 'Create'}
            </button>
          </div>
        </details>

        {/* Search */}
        <details
          open={!brainFirstMode}
          className="hud-panel p-4"
          style={{ order: 4 }}
        >
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
            <span className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
              Notes
            </span>
            <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {selectedTag ? `#${selectedTag}` : searchResults ? `${searchResults.length} results` : `${notes.length} total`}
            </span>
          </summary>
          <div className="mb-3 mt-4 flex items-center gap-2 rounded-md border px-3"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
          >
            <Search size={14} style={{ color: 'var(--color-text-tertiary)' }} />
            <input
              id="vault-search"
              type="text"
              placeholder="Search notes…"
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="h-9 flex-1 bg-transparent text-sm outline-none"
              style={{ color: 'var(--color-text)' }}
            />
          </div>

          <div className="grid gap-2">
            {visibleNotes.length === 0 && (
              <p className="py-4 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {live ? 'No notes yet. Create your first note above.' : 'Backend unavailable — notes will appear here once connected.'}
              </p>
            )}
            {visibleNotes.map((note) => (
              <div
                key={note.id}
                className="flex items-start justify-between gap-3 rounded-md border p-3"
                style={{ borderColor: note.pinned ? 'color-mix(in srgb, var(--color-accent) 35%, transparent)' : 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {note.pinned && <Pin size={12} style={{ color: 'var(--color-accent)' }} />}
                    <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{note.title}</span>
                    <NoteTypeBadge type={note.note_type} />
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {note.tags.slice(0, 4).map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => handleTagFilter(tag)}
                        className="rounded px-1.5 py-0.5 text-xs"
                        style={{ color: 'var(--color-accent)', background: 'var(--color-accent-subtle)' }}
                      >
                        #{tag}
                      </button>
                    ))}
                  </div>
                  <div className="mt-1 text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    {note.date || formatTime(note.created_at)}
                  </div>
                </div>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    onClick={() => handlePin(note)}
                    title={note.pinned ? 'Unpin' : 'Pin'}
                    className="rounded p-1 transition-colors"
                    style={{ color: note.pinned ? 'var(--color-accent)' : 'var(--color-text-tertiary)' }}
                  >
                    <Pin size={13} />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(note.id)}
                    title="Delete"
                    className="rounded p-1 transition-colors"
                    style={{ color: 'var(--color-text-tertiary)' }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </details>

        {/* Graph */}
        <ShellPanel
          title="Brain Graph"
          action={graphStatus ? `${graphStatus.node_count} nodes · ${graphStatus.edge_count} links` : 'offline'}
          className={brainFirstMode ? 'min-h-[calc(100vh-190px)]' : ''}
          style={{ order: 2 }}
        >
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="grid gap-3">
              <div
                className={`relative overflow-hidden rounded-md border ${brainFirstMode ? 'min-h-[720px]' : 'min-h-[560px]'}`}
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <div className="absolute left-4 top-4 z-10 flex items-center gap-2">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-md border"
                    style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-accent)' }}
                  >
                    <Brain size={17} />
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-normal" style={{ color: 'var(--color-text-secondary)' }}>
                      Siri Brain
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
                      {selectedGraphNode ? selectedGraphNode.title : `${graphRoots.length} pinned roots`}
                    </div>
                  </div>
                </div>

                <svg
                  className={`${brainFirstMode ? 'h-[720px]' : 'h-[560px]'} w-full`}
                  viewBox="0 0 760 560"
                  role="img"
                  aria-label="Knowledge graph brain view"
                  preserveAspectRatio="xMidYMid meet"
                >
                  <defs>
                    <filter id="brain-node-shadow" x="-30%" y="-30%" width="160%" height="160%">
                      <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="black" floodOpacity="0.16" />
                    </filter>
                  </defs>
                  <path
                    d="M144 210C116 130 163 54 252 70c48-44 125-30 155 28 42-35 112-20 135 30 79-6 129 59 104 133-18 54-69 82-131 73-42 45-115 44-154-2-46 37-119 30-153-19-32 6-55-1-74-20-21-20-28-48-20-83Z"
                    fill="none"
                    stroke="var(--color-border)"
                    strokeWidth="1.5"
                    strokeDasharray="7 8"
                  />
                  <path
                    d="M382 96C348 132 342 169 362 207c17 32 15 69-12 105"
                    fill="none"
                    stroke="var(--color-border-subtle)"
                    strokeWidth="1"
                    strokeDasharray="5 7"
                  />

                  {brainGraph.edges.map((edge) => {
                    const source = graphNodeById.get(edge.sourceId);
                    const target = graphNodeById.get(edge.targetId);
                    if (!source || !target) return null;
                    const dx = target.x - source.x;
                    const dy = target.y - source.y;
                    const curve = Math.max(-48, Math.min(48, dx * 0.12));
                    const midX = source.x + dx / 2;
                    const midY = source.y + dy / 2 - curve;
                    return (
                      <g key={edge.id}>
                        <path
                          d={`M ${source.x} ${source.y} Q ${midX} ${midY} ${target.x} ${target.y}`}
                          fill="none"
                          stroke={edge.relationship === 'related' ? 'var(--color-border)' : 'color-mix(in srgb, var(--color-accent) 52%, var(--color-border))'}
                          strokeWidth={Math.max(1, Math.min(2.5, edge.strength * 1.6))}
                          strokeOpacity={edge.relationship === 'related' ? 0.55 : 0.75}
                        />
                        {edge.relationship !== 'related' && (
                          <text
                            x={midX}
                            y={midY - 4}
                            textAnchor="middle"
                            fontSize="9"
                            fill="var(--color-text-tertiary)"
                          >
                            {compactGraphLabel(relationLabel(edge.relationship), 14)}
                          </text>
                        )}
                      </g>
                    );
                  })}

                  {brainGraph.nodes.map((visualNode) => {
                    const tone = graphNodeTone(visualNode.kind, visualNode.node?.node_type);
                    const isSelected = selectedGraphNode?.id === visualNode.id;
                    const isLoading = graphLoadingNodeId === visualNode.id;
                    return (
                      <g
                        key={visualNode.id}
                        role={visualNode.node ? 'button' : 'img'}
                        tabIndex={visualNode.node ? 0 : undefined}
                        onMouseEnter={() => setHoveredGraphNodeId(visualNode.id)}
                        onMouseLeave={() => setHoveredGraphNodeId(null)}
                        onFocus={() => setHoveredGraphNodeId(visualNode.id)}
                        onBlur={() => setHoveredGraphNodeId(null)}
                        onClick={() => { if (visualNode.node) void handleGraphNodeSelect(visualNode.node); }}
                        onKeyDown={(event) => {
                          if (!visualNode.node) return;
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            void handleGraphNodeSelect(visualNode.node);
                          }
                        }}
                        style={{ cursor: visualNode.node ? 'pointer' : 'default', outline: 'none' }}
                      >
                        <circle
                          cx={visualNode.x}
                          cy={visualNode.y}
                          r={visualNode.size}
                          fill={tone.fill}
                          stroke={isSelected ? 'var(--color-accent)' : tone.stroke}
                          strokeWidth={isSelected ? 2.5 : 1.4}
                          filter="url(#brain-node-shadow)"
                        />
                        {visualNode.pinnedRoot && (
                          <circle
                            cx={visualNode.x + visualNode.size * 0.62}
                            cy={visualNode.y - visualNode.size * 0.62}
                            r="6"
                            fill="var(--color-success)"
                          />
                        )}
                        {isLoading && (
                          <circle
                            cx={visualNode.x}
                            cy={visualNode.y}
                            r={visualNode.size + 7}
                            fill="none"
                            stroke="var(--color-accent)"
                            strokeWidth="1"
                            strokeDasharray="4 6"
                          />
                        )}
                        <text
                          x={visualNode.x}
                          y={visualNode.y - 2}
                          textAnchor="middle"
                          fontSize={visualNode.kind === 'center' ? 12 : 10}
                          fontWeight={visualNode.kind === 'center' || visualNode.kind === 'root' ? 700 : 600}
                          fill={tone.text}
                        >
                          {compactGraphLabel(visualNode.title, visualNode.kind === 'center' ? 18 : 13)}
                        </text>
                        <text
                          x={visualNode.x}
                          y={visualNode.y + 13}
                          textAnchor="middle"
                          fontSize="8.5"
                          fill="var(--color-text-tertiary)"
                        >
                          {compactGraphLabel(visualNode.subtitle, 12)}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                {brainGraph.nodes.length === 0 && (
                  <div className="absolute inset-0 grid place-items-center px-6 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                    No graph data yet.
                  </div>
                )}

                {activeBrainNode && (
                  <div
                    className="absolute bottom-4 left-4 right-4 grid gap-2 rounded-md border p-3 md:left-auto md:w-[330px]"
                    style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                          {activeBrainNode.title}
                        </div>
                        <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                          {activeGraphNode?.node_type || activeBrainNode.kind}
                          {activeGraphNode?.source ? ` · ${activeGraphNode.source}` : ''}
                        </div>
                      </div>
                      <StatusPill tone={activeBrainNode.pinnedRoot ? 'good' : activeBrainNode.kind === 'timeline' ? 'watch' : 'quiet'}>
                        {activeBrainNode.kind}
                      </StatusPill>
                    </div>
                    {activeGraphNode?.text && (
                      <p className="line-clamp-3 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                        {activeGraphNode.text}
                      </p>
                    )}
                    {activeGraphNode && (
                      <div className="grid grid-cols-2 gap-2 text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
                        <span>{activeGraphLinks.length} visible links</span>
                        <span>{formatTime(activeGraphNode.updated_at)}</span>
                      </div>
                    )}
                    {activeTimelineEvent && (
                      <div className="rounded border px-2 py-1.5 text-xs" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}>
                        {activeTimelineEvent.event_type} · {activeTimelineEvent.title}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <details
                open={!brainFirstMode}
                className="rounded-md border p-3"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
                  <span className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                    Graph Controls
                  </span>
                  <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                    search · roots
                  </span>
                </summary>
                <div className="mt-3 grid gap-3">
                  <div
                    className="flex items-center gap-2 rounded-md border px-3"
                    style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
                  >
                    <GitBranch size={14} style={{ color: 'var(--color-text-tertiary)' }} />
                    <input
                      id="graph-neighborhood-search"
                      type="text"
                      placeholder="Neighborhood search…"
                      value={neighborhoodQuery}
                      onChange={(e) => handleNeighborhoodSearch(e.target.value)}
                      className="h-9 flex-1 bg-transparent text-sm outline-none"
                      style={{ color: 'var(--color-text)' }}
                    />
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {(neighborhoodResults.length ? neighborhoodResults.map((item) => item.node) : graphRoots).map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        onClick={() => handleGraphNodeSelect(node)}
                        className="inline-flex max-w-full items-center gap-2 rounded-md border px-2.5 py-1.5 text-left text-xs"
                        style={{
                          borderColor: selectedGraphNode?.id === node.id ? 'var(--color-accent)' : 'var(--color-border)',
                          background: selectedGraphNode?.id === node.id ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
                          color: 'var(--color-text)',
                        }}
                      >
                        {node.pinned_root && <Pin size={13} style={{ color: 'var(--color-accent)' }} />}
                        <span className="truncate">{node.title}</span>
                      </button>
                    ))}
                    {!neighborhoodResults.length && !graphRoots.length && (
                      <p className="py-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                        No graph roots yet.
                      </p>
                    )}
                  </div>
                </div>
              </details>
            </div>

            <div className="grid content-start gap-3">
              <details open={!brainFirstMode} className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2">
                  <div className="text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                    Focus
                  </div>
                  <StatusPill tone={selectedGraphNode ? 'good' : 'quiet'}>
                    {selectedGraphNode ? selectedGraphNode.node_type : 'roots'}
                  </StatusPill>
                </summary>
                {selectedGraphNode ? (
                  <div className="mt-3 grid gap-2">
                    <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                      {selectedGraphNode.title}
                    </div>
                    {selectedGraphNode.text && (
                      <p className="line-clamp-3 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                        {selectedGraphNode.text}
                      </p>
                    )}
                    <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                      {connectedEdges} links
                    </div>
                    {connectedNodes.slice(0, 4).map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        onClick={() => handleGraphNodeSelect(node)}
                        className="truncate text-left text-xs"
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {node.title}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    {graphRoots.length} pinned roots
                  </p>
                )}
              </details>

              <details open={!brainFirstMode} className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
                <summary className="cursor-pointer list-none text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                  Relationships
                </summary>
                <div className="mt-3 grid gap-2">
                  {relationshipDetails.map(({ edge, source, target, timelineContext }) => (
                    <div key={edge.id} className="grid gap-1 rounded border p-2" style={{ borderColor: 'var(--color-border)' }}>
                      <div className="truncate text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                        {relationLabel(edge.relationship)}
                      </div>
                      <div className="grid gap-0.5 text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
                        <span>source: {source}</span>
                        <span>target: {target}</span>
                        <span>weight {edge.weight.toFixed(1)}</span>
                        {timelineContext && (
                          <span>timeline: {timelineContext.event_type} · {formatTime(timelineContext.occurred_at)}</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {!relationshipSummary.length && (
                    <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      No visible links.
                    </p>
                  )}
                </div>
              </details>

              <details className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
                <summary className="cursor-pointer list-none text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                  Timeline
                </summary>
                <div className="mt-3 grid gap-2">
                  {timeline.slice(0, 4).map((event) => (
                    <div key={event.id}>
                      <div className="truncate text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                        {event.title}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                        {event.event_type} · {formatTime(event.occurred_at)}
                      </div>
                      {event.summary && (
                        <p className="mt-1 line-clamp-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                          {event.summary}
                        </p>
                      )}
                    </div>
                  ))}
                  {!timeline.length && (
                    <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                      No events.
                    </p>
                  )}
                </div>
              </details>

              {timelineRelevantNodes.length > 0 && (
                <details className="rounded-md border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}>
                  <summary className="cursor-pointer list-none text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                    Timeline Nodes
                  </summary>
                  <div className="mt-3 grid gap-1">
                    {timelineRelevantNodes.map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        onClick={() => { if (node.node) void handleGraphNodeSelect(node.node); }}
                        className="truncate text-left text-xs"
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {node.title}
                      </button>
                    ))}
                  </div>
                </details>
              )}
            </div>
          </div>
        </ShellPanel>
      </div>

      {/* Sidebar panels */}
      <details
        open={!brainFirstMode}
        className={brainFirstMode ? 'hud-panel p-4' : 'grid gap-4 content-start'}
      >
        <summary className={brainFirstMode ? 'cursor-pointer list-none text-sm font-semibold' : 'sr-only'} style={{ color: 'var(--color-text)' }}>
          Vault Context
        </summary>
        <div className={brainFirstMode ? 'mt-4 grid gap-4 md:grid-cols-3' : 'contents'}>
        {/* Daily note */}
        <ShellPanel title="Daily Note" action={dailyNote?.date || 'today'}>
          {dailyNote ? (
            <div className="grid gap-2">
              <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                {dailyNote.title}
              </div>
              <p className="line-clamp-4 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {dailyNote.content.replace(/^#[^\n]*\n?/, '').trim() || 'Empty daily note.'}
              </p>
              <div className="flex flex-wrap gap-1">
                {dailyNote.tags.slice(0, 3).map((t) => (
                  <span key={t} className="rounded px-1.5 py-0.5 text-xs" style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent)' }}>#{t}</span>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>No daily note yet.</p>
          )}
        </ShellPanel>

        {/* Tags */}
        <ShellPanel title="Tags" action={`${tags.length} tags`}>
          {tags.length === 0 && (
            <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>No tags yet.</p>
          )}
          <div className="flex flex-wrap gap-2">
            {selectedTag && (
              <button
                type="button"
                onClick={() => handleTagFilter(null)}
                className="rounded-full border px-2.5 py-1 text-xs font-medium"
                style={{ borderColor: 'var(--color-accent)', color: 'var(--color-accent)', background: 'var(--color-accent-subtle)' }}
              >
                × clear
              </button>
            )}
            {tags.slice(0, 20).map((tag) => (
              <button
                key={tag.name}
                type="button"
                onClick={() => handleTagFilter(tag.name)}
                className="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
                style={{
                  borderColor: selectedTag === tag.name ? 'var(--color-accent)' : 'var(--color-border)',
                  color: selectedTag === tag.name ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                  background: selectedTag === tag.name ? 'var(--color-accent-subtle)' : 'var(--color-bg-secondary)',
                }}
              >
                #{tag.name}
                <span className="ml-1 opacity-60">{tag.count}</span>
              </button>
            ))}
          </div>
        </ShellPanel>

        {/* Note type breakdown */}
        <ShellPanel title="By Type">
          <div className="grid gap-2">
            {(['note', 'project', 'research', 'daily'] as const).map((type) => {
              const count = notes.filter((n) => n.note_type === type).length;
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => handleTagFilter(null)}
                  className="flex items-center justify-between rounded-md border px-3 py-2 text-xs"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-secondary)' }}
                >
                  <NoteTypeBadge type={type} />
                  <span style={{ color: 'var(--color-text-tertiary)' }}>{count}</span>
                </button>
              );
            })}
          </div>
        </ShellPanel>
        </div>
      </details>
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
  if (section === 'learning') return <LearningPanel />;
  if (section === 'knowledge-vault') return <KnowledgeVaultSection />;
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
