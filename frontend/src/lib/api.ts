import type { ModelInfo, SavingsData, ServerInfo } from '../types';

// ---------------------------------------------------------------------------
// Supabase config — safe to embed (RLS protects writes)
// ---------------------------------------------------------------------------

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://mtbtgpwzrbostweaanpr.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im10YnRncHd6cmJvc3R3ZWFhbnByIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxODk0OTQsImV4cCI6MjA4ODc2NTQ5NH0._xMlqCfljtXpwPj54H-ghxfLFO-jiq4W2WhpU8vVL1c';

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

export const isTauri = () => typeof window !== 'undefined' && !!window.__TAURI_INTERNALS__;

// Cached API base URL fetched from the Tauri backend at startup.
// This avoids hardcoding the port — the Rust backend is the single
// source of truth for JARVIS_PORT.
let _tauriApiBase: string | null = null;

/** Pre-fetch the API base URL from the Tauri backend (call once at init). */
export async function initApiBase(): Promise<void> {
  if (!isTauri()) return;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    _tauriApiBase = await invoke<string>('get_api_base');
  } catch {
    // Command may not exist on older builds; fall through to default.
  }
}

const DESKTOP_API_FALLBACK = 'http://127.0.0.1:8000';

const getSettingsApiUrl = (): string => {
  try {
    const raw = localStorage.getItem('openjarvis-settings');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed.apiUrl) return parsed.apiUrl.replace(/\/+$/, '');
    }
  } catch {}
  return '';
};

export const getBase = (): string => {
  const settingsUrl = getSettingsApiUrl();
  if (settingsUrl) return settingsUrl;
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (isTauri()) return _tauriApiBase || DESKTOP_API_FALLBACK;
  return '';
};

async function tauriInvoke<T>(command: string, args: Record<string, unknown> = {}): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core');
  const apiUrl = getBase();
  return invoke<T>(command, { apiUrl, ...args });
}

// ---------------------------------------------------------------------------
// Setup status (desktop only)
// ---------------------------------------------------------------------------

export interface SetupStatus {
  phase: string;
  detail: string;
  ollama_ready: boolean;
  server_ready: boolean;
  model_ready: boolean;
  error: string | null;
}

export async function getSetupStatus(): Promise<SetupStatus | null> {
  if (!isTauri()) return null;
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<SetupStatus>('get_setup_status');
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchModels(): Promise<ModelInfo[]> {
  if (isTauri()) {
    try {
      const result = await tauriInvoke<{ data?: ModelInfo[] }>('fetch_models');
      return result?.data || [];
    } catch {
      // Fall through to fetch
    }
  }
  const res = await fetch(`${getBase()}/v1/models`);
  if (!res.ok) throw new Error(`Failed to fetch models: ${res.status}`);
  const data = await res.json();
  return data.data || [];
}

export async function fetchRecommendedModel(): Promise<{ model: string; reason: string }> {
  const res = await fetch(`${getBase()}/v1/recommended-model`);
  if (!res.ok) return { model: '', reason: 'Failed to fetch' };
  return res.json();
}

export async function pullModel(modelName: string): Promise<void> {
  // In Tauri, go through the Rust backend directly (avoids CORS / timeout
  // issues with long model downloads via fetch).
  if (isTauri()) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('pull_ollama_model', { modelName });
      return;
    } catch (e: any) {
      throw new Error(e?.message || e || 'Download failed');
    }
  }
  const res = await fetch(`${getBase()}/v1/models/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: modelName }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Failed to pull model: ${detail}`);
  }
}

export async function deleteModel(modelName: string): Promise<void> {
  if (isTauri()) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('delete_ollama_model', { modelName });
      return;
    } catch (e: any) {
      throw new Error(e?.message || e || 'Delete failed');
    }
  }
  const res = await fetch(`${getBase()}/v1/models/${encodeURIComponent(modelName)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Failed to delete model: ${detail}`);
  }
}

const _CLOUD_PREFIXES = ['gpt-', 'o1-', 'o3-', 'o4-', 'claude-', 'gemini-', 'openrouter/'];

export async function preloadModel(modelName: string): Promise<void> {
  // Cloud models don't need Ollama preloading
  if (_CLOUD_PREFIXES.some(p => modelName.startsWith(p))) {
    return;
  }
  // Trigger Ollama to load the model into memory (empty prompt, no generation).
  const ollamaUrl = 'http://127.0.0.1:11434';
  try {
    const res = await fetch(`${ollamaUrl}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: modelName, prompt: '', keep_alive: '5m' }),
      signal: AbortSignal.timeout(120_000),
    });
    if (!res.ok) throw new Error(`Preload failed: ${res.status}`);
  } catch (e: any) {
    if (e.name === 'TimeoutError') throw new Error('Model load timed out (120s)');
    throw e;
  }
}

export async function fetchSavings(): Promise<SavingsData> {
  const res = await fetch(`${getBase()}/v1/savings`);
  if (!res.ok) throw new Error(`Failed to fetch savings: ${res.status}`);
  return res.json();
}

export async function fetchServerInfo(): Promise<ServerInfo> {
  const res = await fetch(`${getBase()}/v1/info`);
  if (!res.ok) throw new Error(`Failed to fetch server info: ${res.status}`);
  return res.json();
}

export async function checkHealth(): Promise<boolean> {
  if (isTauri()) {
    try {
      await tauriInvoke('check_health', { apiUrl: getBase() });
      return true;
    } catch {
      return false;
    }
  }
  try {
    const res = await fetch(`${getBase()}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchEnergy(): Promise<unknown> {
  if (isTauri()) {
    try {
      return await tauriInvoke('fetch_energy', { apiUrl: getBase() });
    } catch {}
  }
  const res = await fetch(`${getBase()}/v1/telemetry/energy`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function fetchTelemetry(): Promise<unknown> {
  if (isTauri()) {
    try {
      return await tauriInvoke('fetch_telemetry', { apiUrl: getBase() });
    } catch {}
  }
  const res = await fetch(`${getBase()}/v1/telemetry/stats`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function fetchTraces(limit: number = 50): Promise<unknown> {
  if (isTauri()) {
    try {
      return await tauriInvoke('fetch_traces', { apiUrl: getBase(), limit });
    } catch {}
  }
  const res = await fetch(`${getBase()}/v1/traces?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Siri agent workspace
// ---------------------------------------------------------------------------

export interface AgentRoutingMetadata {
  task_classification: string[];
  recommended_agent: string;
  fallback_agent: string;
  multi_agent_compatibility: string[];
}

export interface WorkspaceAgentConfig {
  id: string;
  display_name: string;
  description: string;
  allowed_tools: string[];
  memory_scope: string[];
  permission_ceiling: string;
  preferred_model: string;
  personality_mode: string;
  output_style: string;
  routing: AgentRoutingMetadata;
}

export interface WorkspaceAgentsResponse {
  agents: WorkspaceAgentConfig[];
  active_agent_id: string;
}

export interface ActiveWorkspaceAgentState {
  active_agent_id: string;
  agent: WorkspaceAgentConfig;
}

export async function listWorkspaceAgents(): Promise<WorkspaceAgentsResponse> {
  const res = await fetch(`${getBase()}/v1/agent-workspace/agents`);
  if (!res.ok) throw new Error(`Failed to list workspace agents: ${res.status}`);
  return res.json();
}

export async function getWorkspaceAgentConfig(agentId: string): Promise<WorkspaceAgentConfig> {
  const res = await fetch(
    `${getBase()}/v1/agent-workspace/agents/${encodeURIComponent(agentId)}`,
  );
  if (!res.ok) throw new Error(`Failed to fetch workspace agent: ${res.status}`);
  const data = await res.json();
  return data.agent;
}

export async function getActiveWorkspaceAgent(): Promise<ActiveWorkspaceAgentState> {
  const res = await fetch(`${getBase()}/v1/agent-workspace/active-agent`);
  if (!res.ok) throw new Error(`Failed to fetch active workspace agent: ${res.status}`);
  return res.json();
}

export async function switchActiveWorkspaceAgent(
  agentId: string,
): Promise<ActiveWorkspaceAgentState> {
  const res = await fetch(`${getBase()}/v1/agent-workspace/active-agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId }),
  });
  if (!res.ok) throw new Error(`Failed to switch workspace agent: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Siri operating modes
// ---------------------------------------------------------------------------

export interface SiriModeConfig {
  id: string;
  display_name: string;
  description: string;
  verbosity_level: string;
  proactive_level: string;
  interruption_policy: string;
  preferred_agents: string[];
  memory_behavior: Record<string, unknown>;
  privacy_network_policy: Record<string, unknown>;
  voice_capture_behavior: Record<string, unknown>;
  default_model_overrides: Record<string, unknown>;
  ui_theme_metadata: Record<string, unknown>;
  notification_behavior: Record<string, unknown>;
}

export interface SiriModesResponse {
  modes: SiriModeConfig[];
  active_mode_id: string;
}

export interface ActiveSiriModeState {
  active_mode_id: string;
  mode: SiriModeConfig;
}

export async function listSiriModes(): Promise<SiriModesResponse> {
  const res = await fetch(`${getBase()}/v1/modes`);
  if (!res.ok) throw new Error(`Failed to list Siri modes: ${res.status}`);
  return res.json();
}

export async function getActiveSiriMode(): Promise<ActiveSiriModeState> {
  const res = await fetch(`${getBase()}/v1/modes/active`);
  if (!res.ok) throw new Error(`Failed to fetch active Siri mode: ${res.status}`);
  return res.json();
}

export async function switchActiveSiriMode(modeId: string): Promise<ActiveSiriModeState> {
  const res = await fetch(`${getBase()}/v1/modes/active`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode_id: modeId }),
  });
  if (!res.ok) throw new Error(`Failed to switch Siri mode: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Passive local context
// ---------------------------------------------------------------------------

export interface DesktopContext {
  active_application: string;
  active_window_title: string;
  clipboard_preview: string;
  clipboard_sensitive: boolean;
  current_working_directory: string;
  recent_files: string[];
  privacy_mode: boolean;
  passive_only: boolean;
}

export interface ProjectContext {
  cwd: string;
  git_repository: string;
  current_branch: string;
  languages: string[];
  framework_build_system: string[];
  package_manager: string[];
  project_type: string;
  passive_only: boolean;
}

export interface RepoIndex {
  root: string;
  inventory: string[];
  module_summaries: Array<Record<string, unknown>>;
  dependency_hints: string[];
  architecture_metadata: Record<string, unknown>;
  summary: {
    root: string;
    file_count: number;
    language_breakdown: Record<string, number>;
    top_level_modules: Array<Record<string, unknown>>;
    dependency_hints: string[];
    architecture_metadata: Record<string, unknown>;
  };
  passive_only: boolean;
}

export interface LocalContextSnapshot {
  desktop: DesktopContext;
  project: ProjectContext;
  repo: RepoIndex;
}

export interface ScreenshotMetadata {
  id: string;
  captured_at: string;
  file_path: string;
  format: string;
  width: number | null;
  height: number | null;
  byte_size: number | null;
  sha256: string;
  active_application: string;
  active_window_title: string;
  privacy_mode: boolean;
  redacted: boolean;
  passive_only: boolean;
  local_only: boolean;
}

export interface VisualContext {
  latest_screenshot: ScreenshotMetadata | null;
  screenshot_count: number;
  privacy_mode: boolean;
  passive_only: boolean;
  local_only: boolean;
  cloud_uploaded: boolean;
}

export interface ScreenshotCaptureResponse {
  screenshot: ScreenshotMetadata;
  privacy_mode: boolean;
  passive_only: boolean;
  local_only: boolean;
  cloud_uploaded: boolean;
}

export interface SuggestedTerminalCommand {
  id: string;
  command: string;
  reason: string;
  safety: string;
  permission_level: string;
  permission_action: string;
  requires_approval: boolean;
  dangerous: boolean;
  matched_pattern: string | null;
  dry_run_preview: Record<string, unknown>;
}

export interface TerminalErrorSummary {
  has_error: boolean;
  summary: string;
  patterns: string[];
  possible_fixes: string[];
  suggested_commands: SuggestedTerminalCommand[];
  local_only: boolean;
  passive_only: boolean;
}

export interface TerminalCommandRecord {
  command: string;
  output: string;
  exit_code: number | null;
  cwd: string;
  repo_context: Record<string, unknown>;
  shell_type: string;
  timestamp: string;
  output_preview: string;
  passive_only: boolean;
  local_only: boolean;
}

export interface TerminalContextSnapshot {
  current: TerminalCommandRecord | null;
  history: TerminalCommandRecord[];
  error_summary: TerminalErrorSummary;
  cwd: string;
  shell_type: string;
  project_context: ProjectContext;
  privacy_mode: boolean;
  passive_only: boolean;
  local_only: boolean;
}

export async function fetchDesktopContext(): Promise<DesktopContext> {
  const res = await fetch(`${getBase()}/v1/context/desktop`);
  if (!res.ok) throw new Error(`Failed to fetch desktop context: ${res.status}`);
  return res.json();
}

export async function fetchProjectContext(): Promise<ProjectContext> {
  const res = await fetch(`${getBase()}/v1/context/project`);
  if (!res.ok) throw new Error(`Failed to fetch project context: ${res.status}`);
  return res.json();
}

export async function fetchRepoContext(): Promise<RepoIndex> {
  const res = await fetch(`${getBase()}/v1/context/repo`);
  if (!res.ok) throw new Error(`Failed to fetch repo context: ${res.status}`);
  return res.json();
}

export async function fetchLocalContextSnapshot(): Promise<LocalContextSnapshot> {
  const [desktop, project, repo] = await Promise.all([
    fetchDesktopContext(),
    fetchProjectContext(),
    fetchRepoContext(),
  ]);
  return { desktop, project, repo };
}

export async function captureVisionScreenshot(): Promise<ScreenshotCaptureResponse> {
  const res = await fetch(`${getBase()}/v1/context/vision/screenshots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_approval_on_privacy: true }),
  });
  if (!res.ok) throw new Error(`Failed to capture screenshot: ${res.status}`);
  return res.json();
}

export async function fetchRecentVisionScreenshots(limit = 10): Promise<ScreenshotMetadata[]> {
  const res = await fetch(`${getBase()}/v1/context/vision/screenshots?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch screenshots: ${res.status}`);
  const data = await res.json();
  return data.screenshots || [];
}

export async function fetchLatestVisualContext(): Promise<VisualContext> {
  const res = await fetch(`${getBase()}/v1/context/vision/latest`);
  if (!res.ok) throw new Error(`Failed to fetch visual context: ${res.status}`);
  return res.json();
}

export async function fetchTerminalContext(): Promise<TerminalContextSnapshot> {
  const res = await fetch(`${getBase()}/v1/context/terminal/current`);
  if (!res.ok) throw new Error(`Failed to fetch terminal context: ${res.status}`);
  return res.json();
}

export async function fetchTerminalHistory(limit = 20): Promise<TerminalCommandRecord[]> {
  const res = await fetch(`${getBase()}/v1/context/terminal/history?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch terminal history: ${res.status}`);
  const data = await res.json();
  return data.history || [];
}

export async function fetchTerminalSuggestedFixes(): Promise<TerminalErrorSummary> {
  const res = await fetch(`${getBase()}/v1/context/terminal/suggested-fixes`);
  if (!res.ok) throw new Error(`Failed to fetch terminal fixes: ${res.status}`);
  return res.json();
}

export async function requestTerminalCommandApproval(commandId: string): Promise<{
  approval: SecurityApproval;
  suggested_command: SuggestedTerminalCommand;
  executed: boolean;
  passive_only: boolean;
}> {
  const res = await fetch(`${getBase()}/v1/context/terminal/suggested-commands/${commandId}/approval`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Security approvals
// ---------------------------------------------------------------------------

export interface SecurityApproval {
  id: string;
  status: 'pending' | 'approved' | 'denied';
  requested_at: string;
  decided_at: string | null;
  tool: string;
  agent_id: string;
  source: string;
  level: string;
  reason: string;
  matched_pattern: string | null;
  argument_keys: string[];
  command_preview: string;
  decision?: string | null;
  decision_note?: string;
}

export interface PermissionAuditEvent {
  timestamp: string;
  agent_id: string;
  tool: string;
  action: string;
  level: string;
  reason: string;
  matched_pattern: string | null;
  command_preview: string;
  request_metadata?: Record<string, unknown>;
}

export async function fetchSecurityApprovals(
  status: 'pending' | 'approved' | 'denied' | 'all' = 'pending',
  limit = 50,
): Promise<SecurityApproval[]> {
  const res = await fetch(`${getBase()}/v1/security/approvals?status=${status}&limit=${limit}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.approvals || [];
}

export async function decideSecurityApproval(
  approvalId: string,
  decision: 'approve' | 'deny',
  note = '',
): Promise<SecurityApproval> {
  const res = await fetch(`${getBase()}/v1/security/approvals/${approvalId}/${decision}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function fetchPermissionAudit(limit = 100): Promise<PermissionAuditEvent[]> {
  const res = await fetch(`${getBase()}/v1/security/permissions/audit?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.events || [];
}

// ---------------------------------------------------------------------------
// Speech
// ---------------------------------------------------------------------------

export interface TranscriptionResult {
  text: string;
  language: string | null;
  confidence: number | null;
  duration_seconds: number;
}

export interface SpeechHealth {
  available: boolean;
  backend?: string;
  reason?: string;
}

export interface VoiceIntentPreview {
  transcript: string;
  interpreted_intent: string;
  planned_actions: string[];
  risk_level: string;
  approval_required: boolean;
}

export interface VoiceSession {
  id: string;
  status: string;
  started_at: number;
  stopped_at: number | null;
  duration: number;
  duration_seconds: number;
  audio_path: string;
  transcript: string;
  active_agent: string;
  active_mode: string;
  permission_decisions: Array<Record<string, unknown>>;
  invoked_tools: string[];
  persisted_raw_audio: boolean;
  raw_audio_available: boolean;
  byte_size: number;
  backend: string;
  intent_preview: VoiceIntentPreview | null;
  context: Record<string, unknown>;
}

export interface VoicePttStatus {
  state: 'idle' | 'recording' | string;
  recording: boolean;
  push_to_talk_only: boolean;
  wake_word_enabled: boolean;
  passive_listening: boolean;
  capture_enabled: boolean;
  requires_explicit_approval: boolean;
  privacy_mode: boolean;
  active_mode_id: string;
  active_agent_id: string;
  transcription_available: boolean;
  latest: VoiceSession | null;
}

export interface VoicePttStartResponse {
  status: VoicePttStatus;
  session: VoiceSession;
  recording: VoiceSession;
}

export interface VoiceTranscriptResult extends TranscriptionResult {
  status: string;
  reason?: string;
  intent_preview?: VoiceIntentPreview;
  session: VoiceSession;
  metadata: VoiceSession;
  passive_only: boolean;
  dispatched_to_agent: boolean;
}

export async function transcribeAudio(audioBlob: Blob, filename = 'recording.webm'): Promise<TranscriptionResult> {
  if (isTauri()) {
    try {
      const buffer = await audioBlob.arrayBuffer();
      return await tauriInvoke<TranscriptionResult>('transcribe_audio', {
        audioData: Array.from(new Uint8Array(buffer)),
        filename,
      });
    } catch {
      // Fall through to fetch
    }
  }
  const formData = new FormData();
  formData.append('file', audioBlob, filename);
  const res = await fetch(`${getBase()}/v1/speech/transcribe`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(`Transcription failed: ${res.status}`);
  return res.json();
}

export async function fetchSpeechHealth(): Promise<SpeechHealth> {
  if (isTauri()) {
    try {
      return await tauriInvoke<SpeechHealth>('speech_health');
    } catch {
      return { available: false };
    }
  }
  const res = await fetch(`${getBase()}/v1/speech/health`);
  if (!res.ok) return { available: false };
  return res.json();
}

export async function fetchVoicePttStatus(): Promise<VoicePttStatus> {
  const res = await fetch(`${getBase()}/v1/voice/ptt/status`);
  if (!res.ok) throw new Error(`Failed to fetch voice status: ${res.status}`);
  return res.json();
}

export async function startVoicePttRecording(agentId = ''): Promise<VoicePttStartResponse> {
  const res = await fetch(`${getBase()}/v1/voice/ptt/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, approved: true }),
  });
  if (!res.ok) throw new Error(`Failed to start voice recording: ${res.status}`);
  return res.json();
}

export async function stopVoicePttRecording(): Promise<VoicePttStartResponse> {
  const res = await fetch(`${getBase()}/v1/voice/ptt/stop`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to stop voice recording: ${res.status}`);
  return res.json();
}

export async function transcribeLatestVoiceRecording(): Promise<VoiceTranscriptResult> {
  const res = await fetch(`${getBase()}/v1/voice/ptt/transcribe-latest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`Failed to transcribe voice recording: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Agent Manager
// ---------------------------------------------------------------------------

export interface ManagedAgent {
  id: string;
  name: string;
  agent_type: string;
  config: Record<string, unknown>;
  status: 'idle' | 'running' | 'paused' | 'error' | 'archived' | 'needs_attention' | 'budget_exceeded' | 'stalled';
  summary_memory: string;
  created_at: number;
  updated_at: number;
  // Runtime stats
  total_runs?: number;
  total_cost?: number;
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  last_run_at?: number | null;
  // Schedule
  schedule_type?: string;
  schedule_value?: string;
  // Budget
  budget?: number;
  // Learning
  learning_enabled?: boolean;
  // Live progress
  current_activity?: string;
}

export interface AgentTask {
  id: string;
  agent_id: string;
  description: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
  progress: Record<string, unknown>;
  findings: unknown[];
  created_at: number;
}

export interface ChannelBinding {
  id: string;
  agent_id: string;
  channel_type: string;
  config: Record<string, unknown>;
  session_id: string;
  routing_mode: string;
}

export interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  source: 'built-in' | 'user';
  agent_type: string;
  [key: string]: unknown;
}

export interface PersistedToolCall {
  tool: string;
  arguments: string;
  result?: string;
  success?: boolean;
  latency?: number;
}

export interface AgentMessage {
  id: string;
  agent_id: string;
  direction: 'user_to_agent' | 'agent_to_user';
  content: string;
  mode: 'immediate' | 'queued';
  status: 'pending' | 'delivered' | 'responded';
  created_at: number;
  tool_calls?: PersistedToolCall[] | null;
}

export async function fetchManagedAgents(): Promise<ManagedAgent[]> {
  const res = await fetch(`${getBase()}/v1/managed-agents`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.agents || [];
}

export async function fetchManagedAgent(agentId: string): Promise<ManagedAgent> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function createManagedAgent(body: {
  name: string;
  agent_type?: string;
  template_id?: string;
  config?: Record<string, unknown>;
}): Promise<ManagedAgent> {
  const res = await fetch(`${getBase()}/v1/managed-agents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function updateManagedAgent(
  agentId: string,
  body: Partial<{ name: string; agent_type: string; config: Record<string, unknown> }>,
): Promise<ManagedAgent> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function deleteManagedAgent(agentId: string): Promise<void> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
}

export async function pauseManagedAgent(agentId: string): Promise<void> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/pause`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
}

export async function resumeManagedAgent(agentId: string): Promise<void> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/resume`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
}

export async function fetchAgentTasks(agentId: string): Promise<AgentTask[]> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/tasks`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.tasks || [];
}

export async function createAgentTask(agentId: string, description: string): Promise<AgentTask> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function fetchAgentChannels(agentId: string): Promise<ChannelBinding[]> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/channels`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.bindings || [];
}

export async function bindAgentChannel(
  agentId: string,
  channelType: string,
  config?: Record<string, unknown>,
): Promise<ChannelBinding> {
  const res = await fetch(
    `${getBase()}/v1/managed-agents/${agentId}/channels`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_type: channelType,
        config: config || {},
        routing_mode: 'dedicated',
      }),
    },
  );
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export async function unbindAgentChannel(
  agentId: string,
  bindingId: string,
): Promise<void> {
  const res = await fetch(
    `${getBase()}/v1/managed-agents/${agentId}/channels/${bindingId}`,
    { method: 'DELETE' },
  );
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
}

// -- SendBlue auto-setup helpers ------------------------------------------

export async function sendblueVerify(
  apiKeyId: string,
  apiSecretKey: string,
): Promise<{ valid: boolean; numbers: string[]; raw: unknown }> {
  const res = await fetch(`${getBase()}/v1/channels/sendblue/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key_id: apiKeyId, api_secret_key: apiSecretKey }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Verification failed: ${res.status}`);
  }
  return res.json();
}

export async function sendblueRegisterWebhook(
  apiKeyId: string,
  apiSecretKey: string,
  webhookUrl: string,
): Promise<{ registered: boolean; status: number }> {
  const res = await fetch(`${getBase()}/v1/channels/sendblue/register-webhook`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key_id: apiKeyId,
      api_secret_key: apiSecretKey,
      webhook_url: webhookUrl,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Webhook registration failed: ${res.status}`);
  }
  return res.json();
}

export async function sendblueTest(
  apiKeyId: string,
  apiSecretKey: string,
  fromNumber: string,
  toNumber: string,
): Promise<{ sent: boolean; status: number }> {
  const res = await fetch(`${getBase()}/v1/channels/sendblue/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key_id: apiKeyId,
      api_secret_key: apiSecretKey,
      from_number: fromNumber,
      to_number: toNumber,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Test message failed: ${res.status}`);
  }
  return res.json();
}

export async function sendblueHealth(): Promise<{ channel_connected: boolean; bridge_wired: boolean; ready: boolean }> {
  const res = await fetch(`${getBase()}/v1/channels/sendblue/health`);
  if (!res.ok) return { channel_connected: false, bridge_wired: false, ready: false };
  return res.json();
}

export async function fetchTemplates(): Promise<AgentTemplate[]> {
  const res = await fetch(`${getBase()}/v1/templates`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.templates || [];
}

export async function runManagedAgent(agentId: string): Promise<void> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/run`, { method: 'POST' });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Failed: ${res.status}`);
  }
}

export async function recoverManagedAgent(agentId: string): Promise<{ recovered: boolean; checkpoint: unknown }> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/recover`, { method: 'POST' });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchAgentState(agentId: string): Promise<{
  agent: ManagedAgent;
  tasks: AgentTask[];
  channels: ChannelBinding[];
  messages: AgentMessage[];
  checkpoint: unknown;
}> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/state`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

export interface AgentToolCallStart {
  tool: string;
  arguments: string;
}

export interface AgentToolCallEnd {
  tool: string;
  success: boolean;
  latency: number;
  result?: string;
}

export async function sendAgentMessage(
  agentId: string,
  content: string,
  mode: 'immediate' | 'queued' = 'queued',
  callbacks?: {
    onProgress?: (label: string) => void;
    onContentDelta?: (delta: string, fullContent: string) => void;
    onToolCallStart?: (info: AgentToolCallStart) => void;
    onToolCallEnd?: (info: AgentToolCallEnd) => void;
    onDone?: (fullContent: string, usage?: Record<string, number>, telemetry?: Record<string, unknown>) => void;
  },
): Promise<AgentMessage> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, mode, stream: true }),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);

  // If streaming, consume the SSE response so the agent runs
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('text/event-stream') && res.body) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';
    let buffer = '';
    let lastUsage: Record<string, number> | undefined;
    let lastTelemetry: Record<string, unknown> | undefined;
    let currentEvent: string | undefined;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
            continue;
          }
          if (!line.startsWith('data: ')) {
            if (line.trim() === '') currentEvent = undefined;
            continue;
          }
          const data = line.slice(6);
          if (data === '[DONE]') {
            currentEvent = undefined;
            continue;
          }
          const evName = currentEvent;
          currentEvent = undefined;

          if (evName === 'tool_call_start') {
            try {
              const parsed = JSON.parse(data);
              callbacks?.onToolCallStart?.({
                tool: parsed.tool,
                arguments: parsed.arguments ?? '',
              });
            } catch {
              /* skip */
            }
            continue;
          }
          if (evName === 'tool_call_end') {
            try {
              const parsed = JSON.parse(data);
              callbacks?.onToolCallEnd?.({
                tool: parsed.tool,
                success: !!parsed.success,
                latency: typeof parsed.latency === 'number' ? parsed.latency : 0,
                result: parsed.result,
              });
            } catch {
              /* skip */
            }
            continue;
          }

          try {
            const chunk = JSON.parse(data);
            // Deep-research branch still uses tool_progress in a data chunk
            const toolProgress = chunk.choices?.[0]?.tool_progress;
            if (toolProgress) {
              callbacks?.onProgress?.(toolProgress);
            }
            const delta = chunk.choices?.[0]?.delta?.content || '';
            if (delta) {
              fullContent += delta;
              callbacks?.onContentDelta?.(delta, fullContent);
            }
            if (chunk.usage) lastUsage = chunk.usage;
            if (chunk.telemetry) lastTelemetry = chunk.telemetry;
          } catch {
            /* skip malformed chunks */
          }
        }
      }
    } catch { /* stream ended */ }

    callbacks?.onDone?.(fullContent, lastUsage, lastTelemetry);

    return {
      id: '',
      agent_id: agentId,
      direction: 'agent_to_user',
      content: fullContent,
      mode,
      status: 'delivered',
      created_at: Date.now() / 1000,
    };
  }

  return res.json();
}

export async function fetchAgentMessages(agentId: string): Promise<AgentMessage[]> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/messages`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.messages || [];
}

export async function fetchErrorAgents(): Promise<ManagedAgent[]> {
  const res = await fetch(`${getBase()}/v1/agents/errors`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.agents || [];
}

// ---------------------------------------------------------------------------
// Agent Learning + Traces
// ---------------------------------------------------------------------------

export interface LearningLogEntry {
  id: string;
  agent_id: string;
  event_type: string;
  description: string;
  data: Record<string, unknown>;
  created_at: number;
}

export interface AgentTrace {
  id: string;
  outcome: string;
  duration: number;
  started_at: number;
  steps: number;
  error_message?: string;
  metadata?: Record<string, unknown>;
}

export interface ToolInfo {
  name: string;
  description: string;
  category: string;
  source: 'tool' | 'channel';
  requires_credentials: boolean;
  credential_keys: string[];
  configured: boolean;
}

export async function fetchAvailableTools(): Promise<ToolInfo[]> {
  const res = await fetch(`${getBase()}/v1/tools`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.tools || [];
}

export async function saveToolCredentials(
  toolName: string,
  credentials: Record<string, string>,
): Promise<void> {
  const res = await fetch(`${getBase()}/v1/tools/${toolName}/credentials`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
}

export interface AgentTraceDetail {
  id: string;
  agent: string;
  outcome: string;
  duration: number;
  started_at: number;
  steps: Array<{
    step_type: string;
    input: unknown;
    output: string;
    duration: number;
    metadata: Record<string, unknown>;
  }>;
}

export async function fetchLearningLog(agentId: string): Promise<LearningLogEntry[]> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/learning`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.learning_log || [];
}

export async function triggerLearning(agentId: string): Promise<void> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/learning/run`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
}

export async function fetchAgentTraces(agentId: string, limit = 20): Promise<AgentTrace[]> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/traces?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  const data = await res.json();
  return data.traces || [];
}

export async function fetchAgentTrace(agentId: string, traceId: string): Promise<AgentTraceDetail> {
  const res = await fetch(`${getBase()}/v1/managed-agents/${agentId}/traces/${traceId}`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Leaderboard savings submission (Supabase)
// ---------------------------------------------------------------------------

export interface SavingsSubmission {
  anon_id: string;
  display_name: string;
  email: string;
  total_calls: number;
  total_tokens: number;
  dollar_savings: number;
  energy_wh_saved: number;
  flops_saved: number;
  token_counting_version?: number;
}

export async function submitSavings(data: SavingsSubmission): Promise<boolean> {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return false;
  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/savings_entries?on_conflict=anon_id`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
          Prefer: 'resolution=merge-duplicates',
        },
        body: JSON.stringify(data),
      },
    );
    return res.ok || res.status === 201 || res.status === 200;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

export interface MemorySearchResult {
  id?: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
  memory_type?: string;
  project_id?: string | null;
  tags?: string[];
  pinned?: boolean;
  created_at?: string;
  updated_at?: string;
  source?: MemorySource | null;
}

export interface MemorySource {
  id?: string;
  title: string;
  url: string;
  timestamp?: string;
  relevance?: number;
  tags?: string[];
}

export interface StructuredMemory {
  id: string;
  content: string;
  memory_type: string;
  project_id: string | null;
  metadata: Record<string, unknown>;
  tags: string[];
  pinned: boolean;
  created_at: string;
  updated_at: string;
  source: MemorySource | null;
}

export interface MemoryStats {
  entries: number;
  backend: string;
  [key: string]: unknown;
}

export interface MemoryConfig {
  backend: string;
  context_from_memory: boolean;
  context_top_k: number;
  context_min_score: number;
  context_max_tokens: number;
}

export async function getMemoryStats(): Promise<MemoryStats> {
  const res = await fetch(`${getBase()}/v1/memory/stats`);
  if (!res.ok) throw new Error('Failed to fetch memory stats');
  return res.json();
}

export async function searchMemory(query: string, topK: number = 5): Promise<MemorySearchResult[]> {
  const res = await fetch(`${getBase()}/v1/memory/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error('Failed to search memory');
  const data = await res.json();
  return data.results;
}

export async function listMemories(params: {
  project_id?: string;
  memory_type?: string;
  created_after?: string;
  created_before?: string;
  pinned?: boolean;
  limit?: number;
  offset?: number;
} = {}): Promise<StructuredMemory[]> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) searchParams.set(key, String(value));
  });
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
  const res = await fetch(`${getBase()}/v1/memory${suffix}`);
  if (!res.ok) throw new Error('Failed to list memories');
  const data = await res.json();
  return data.memories;
}

export async function createMemory(data: {
  content: string;
  memory_type?: string;
  project_id?: string | null;
  metadata?: Record<string, unknown>;
  tags?: string[];
  source?: MemorySource | null;
  pinned?: boolean;
}): Promise<StructuredMemory> {
  const res = await fetch(`${getBase()}/v1/memory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create memory');
  const body = await res.json();
  return body.memory;
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const res = await fetch(`${getBase()}/v1/memory/${encodeURIComponent(memoryId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete memory');
}

export async function setMemoryPinned(memoryId: string, pinned: boolean): Promise<StructuredMemory> {
  const res = await fetch(`${getBase()}/v1/memory/${encodeURIComponent(memoryId)}/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pinned }),
  });
  if (!res.ok) throw new Error('Failed to update memory pin');
  const body = await res.json();
  return body.memory;
}

export async function storeMemory(
  content: string,
  metadata?: Record<string, unknown>,
): Promise<void> {
  const res = await fetch(`${getBase()}/v1/memory/store`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, metadata }),
  });
  if (!res.ok) throw new Error('Failed to store memory');
}

export async function indexMemoryPath(path: string): Promise<{ chunks_indexed: number }> {
  const res = await fetch(`${getBase()}/v1/memory/index`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) throw new Error('Failed to index path');
  return res.json();
}

export async function getMemoryConfig(): Promise<MemoryConfig> {
  const res = await fetch(`${getBase()}/v1/memory/config`);
  if (!res.ok) throw new Error('Failed to fetch memory config');
  return res.json();
}
