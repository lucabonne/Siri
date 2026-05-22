import {
  Activity,
  Bot,
  Brain,
  BookMarked,
  CalendarDays,
  Camera,
  CheckSquare,
  Code2,
  FileSearch,
  FolderKanban,
  FolderGit2,
  Globe2,
  Home,
  KeyRound,
  ListChecks,
  Mic2,
  Newspaper,
  Settings,
  TerminalSquare,
  BookOpen,
} from 'lucide-react';
import type {
  ApprovalRecord,
  MissionAgent,
  MissionFeedItem,
  MissionMetric,
  MissionMemory,
  MissionProject,
  MissionSection,
  MissionTask,
  PermissionEvent,
} from './types';

export const missionSections: MissionSection[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'today', label: 'Today', icon: CalendarDays },
  { id: 'world-map', label: 'World Map', icon: Globe2 },
  { id: 'daily-briefing', label: 'Daily Briefing', icon: Newspaper },
  { id: 'important-events', label: 'Important Events', icon: ListChecks },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare },
  { id: 'agents', label: 'Agents', icon: Bot },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'projects', label: 'Projects', icon: FolderKanban },
  { id: 'coding', label: 'Coding', icon: Code2 },
  { id: 'repo', label: 'Repo', icon: FolderGit2 },
  { id: 'voice', label: 'Voice', icon: Mic2 },
  { id: 'vision', label: 'Vision', icon: Camera },
  { id: 'terminal', label: 'Terminal', icon: TerminalSquare },
  { id: 'research', label: 'Research', icon: FileSearch },
  { id: 'learning', label: 'Learning', icon: BookOpen },
  { id: 'knowledge-vault', label: 'Knowledge Vault', icon: BookMarked },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'permissions', label: 'Permissions', icon: KeyRound },
];

export const missionMetrics: MissionMetric[] = [
  {
    label: 'Focus queue',
    value: '7',
    detail: '2 waiting on approval',
    tone: 'busy',
  },
  {
    label: 'Active agents',
    value: '4',
    detail: 'research, coding, planning, ops',
    tone: 'good',
  },
  {
    label: 'Memory graph',
    value: '18.2k',
    detail: 'fresh links indexed today',
    tone: 'quiet',
  },
  {
    label: 'Permission gate',
    value: '3',
    detail: 'events need review',
    tone: 'watch',
  },
];

export const missionFeed: MissionFeedItem[] = [
  {
    time: '09:10',
    title: 'Morning brief assembled',
    detail: 'Calendar, inbox, and active projects are staged for review.',
    tone: 'good',
  },
  {
    time: '09:32',
    title: 'Terminal command paused',
    detail: 'A shell-style operation is waiting for explicit approval.',
    tone: 'watch',
  },
  {
    time: '10:05',
    title: 'Research sweep complete',
    detail: 'Three new source clusters are ready in the research lane.',
    tone: 'quiet',
  },
  {
    time: '10:42',
    title: 'Project handoff prepared',
    detail: 'Mission Control draft notes are grouped for the next pass.',
    tone: 'busy',
  },
];

export const missionTasks: MissionTask[] = [
  {
    title: 'Ship dashboard shell',
    owner: 'Design agent',
    state: 'Running',
    due: 'Today',
  },
  {
    title: 'Review permission audit copy',
    owner: 'Security agent',
    state: 'Review',
    due: 'Today',
  },
  {
    title: 'Map project memory tags',
    owner: 'Memory agent',
    state: 'Queued',
    due: 'Tomorrow',
  },
  {
    title: 'Clean terminal command presets',
    owner: 'Ops agent',
    state: 'Done',
    due: 'Yesterday',
  },
];

export const missionAgents: MissionAgent[] = [
  { name: 'Atlas', role: 'Research', status: 'Scanning', load: 72 },
  { name: 'Vega', role: 'Coding', status: 'Composing', load: 64 },
  { name: 'Nova', role: 'Planning', status: 'Idle', load: 18 },
  { name: 'Orion', role: 'Ops', status: 'Awaiting approval', load: 39 },
];

export const missionProjects: MissionProject[] = [
  {
    name: 'Mission Control',
    status: 'Shell build',
    progress: 58,
    next: 'Wire real data adapters',
  },
  {
    name: 'Permission Layer',
    status: 'Phase 2 merged',
    progress: 82,
    next: 'Add approval UX',
  },
  {
    name: 'Memory Studio',
    status: 'Discovery',
    progress: 36,
    next: 'Draft tag model',
  },
];

export const missionMemories: MissionMemory[] = [
  {
    id: 'mock-memory-permissions',
    content: 'Phase 2 permission notes',
    memory_type: 'decision',
    tags: ['permissions'],
    pinned: true,
    created_at: new Date(Date.now() - 42 * 60 * 1000).toISOString(),
    source: null,
  },
  {
    id: 'mock-memory-sources',
    content: 'Desktop source setup',
    memory_type: 'project',
    tags: ['desktop'],
    pinned: false,
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    source: null,
  },
  {
    id: 'mock-memory-branding',
    content: 'Siri branding pass',
    memory_type: 'note',
    tags: ['siri'],
    pinned: false,
    created_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    source: null,
  },
];

export const permissionEvents: PermissionEvent[] = [
  {
    tool: 'shell_exec',
    action: 'Blocked',
    source: 'server_streaming',
    time: '09:32',
  },
  {
    tool: 'file_read',
    action: 'Allowed',
    source: 'mcp',
    time: '09:48',
  },
  {
    tool: 'run_command',
    action: 'Needs approval',
    source: 'terminal',
    time: '10:17',
  },
];

export const approvalQueue: ApprovalRecord[] = [
  {
    id: 'demo-shell-approval',
    status: 'pending',
    requested_at: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
    decided_at: null,
    tool: 'shell_exec',
    agent_id: 'orion',
    source: 'server_streaming',
    level: 'CONFIRMED_EXECUTION',
    reason: 'shell command requires confirmation',
    matched_pattern: null,
    argument_keys: ['command'],
    command_preview: 'git status --short',
  },
  {
    id: 'demo-write-approval',
    status: 'pending',
    requested_at: new Date(Date.now() - 19 * 60 * 1000).toISOString(),
    decided_at: null,
    tool: 'file_write',
    agent_id: 'vega',
    source: 'tool_executor',
    level: 'CONFIRMED_EXECUTION',
    reason: 'tool requires confirmation',
    matched_pattern: null,
    argument_keys: ['path', 'content'],
    command_preview: '',
  },
];

export const worldSignals = [
  { city: 'Rome', label: 'Home base', x: '50%', y: '42%', tone: 'good' },
  { city: 'New York', label: 'Market brief', x: '27%', y: '38%', tone: 'busy' },
  { city: 'Tokyo', label: 'Research watch', x: '79%', y: '44%', tone: 'watch' },
  { city: 'Sydney', label: 'Night digest', x: '83%', y: '71%', tone: 'quiet' },
] as const;

export const quickCommands = [
  { icon: Activity, label: 'Run daily sweep' },
  { icon: Brain, label: 'Open memory lane' },
  { icon: TerminalSquare, label: 'Review terminal gate' },
  { icon: FileSearch, label: 'Start research brief' },
];
