import {
  Activity,
  Bot,
  Brain,
  BookMarked,
  CalendarDays,
  CheckSquare,
  FileSearch,
  FolderKanban,
  Globe2,
  Home,
  KeyRound,
  Settings,
  TerminalSquare,
  BookOpen,
  Wrench,
  Workflow,
  User,
  Cpu,
} from 'lucide-react';
import type {
  MissionAgent,
  MissionFeedItem,
  MissionMemory,
  MissionMetric,
  MissionProject,
  MissionSection,
  MissionTask,
  PermissionEvent,
  ResearchItem,
  TerminalSignal,
  WorldSignal,
} from './types';

export const missionSections: MissionSection[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'today', label: 'Today', icon: CalendarDays },
  { id: 'world-map', label: 'World Map', icon: Globe2 },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare },
  { id: 'agents', label: 'Agents', icon: Bot },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'projects', label: 'Projects', icon: FolderKanban },
  { id: 'terminal', label: 'Terminal', icon: TerminalSquare },
  { id: 'research', label: 'Research', icon: FileSearch },
  { id: 'learning', label: 'Learning', icon: BookOpen },
  { id: 'release', label: 'Release', icon: ShieldCheck },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'personalization', label: 'Personalization', icon: User },
  { id: 'permissions', label: 'Permissions', icon: KeyRound },
  { id: 'autonomy', label: 'Autonomy', icon: Cpu },
];

export const missionMetrics: MissionMetric[] = [
  {
    label: 'Current mode',
    value: 'Focus',
    detail: 'Quiet planning, clear next actions',
    tone: 'good',
  },
  {
    label: 'Active project',
    value: 'Siri',
    detail: 'Mission Control phase 1',
    tone: 'busy',
  },
  {
    label: 'Running agents',
    value: '4',
    detail: 'orchestrator, coding, research, security',
    tone: 'good',
  },
  {
    label: 'Permission queue',
    value: '2',
    detail: 'execution requests waiting',
    tone: 'watch',
  },
];

export const missionFeed: MissionFeedItem[] = [
  {
    time: '08:45',
    title: 'Morning briefing staged',
    detail: 'Calendar, project notes, and local context are ready for review.',
    tone: 'good',
  },
  {
    time: '09:10',
    title: 'Permission model drafted',
    detail: 'Levels 0-3 are queued as the next local-first security pass.',
    tone: 'busy',
  },
  {
    time: '09:35',
    title: 'Terminal error captured',
    detail: 'A failed build command is pinned for later diagnosis.',
    tone: 'watch',
  },
  {
    time: '10:05',
    title: 'Memory note linked',
    detail: 'Second Brain export requirements were added to the project lane.',
    tone: 'quiet',
  },
];

export const missionTasks: MissionTask[] = [
  {
    title: 'Build Mission Control shell',
    owner: 'Interface layer',
    state: 'Running',
    due: 'Today',
    tone: 'busy',
  },
  {
    title: 'Keep internal OpenJarvis identifiers stable',
    owner: 'Core layer',
    state: 'Pinned',
    due: 'Always',
    tone: 'good',
  },
  {
    title: 'Draft permission levels',
    owner: 'Security agent',
    state: 'Queued',
    due: 'Next',
    tone: 'watch',
  },
  {
    title: 'Shape Knowledge Vault import/export',
    owner: 'Memory layer',
    state: 'Review',
    due: 'Soon',
    tone: 'quiet',
  },
];

export const missionAgents: MissionAgent[] = [
  { name: 'Orchestrator', role: 'Routing', status: 'Coordinating', load: 68, tone: 'busy' },
  { name: 'Coding', role: 'Developer', status: 'Ready', load: 44, tone: 'good' },
  { name: 'Research', role: 'Sources', status: 'Idle', load: 18, tone: 'quiet' },
  { name: 'Security', role: 'Permissions', status: 'Watching', load: 52, tone: 'watch' },
];

export const missionMemories: MissionMemory[] = [
  {
    title: 'Second Brain belongs inside Memory Layer',
    type: 'decision',
    tags: ['memory', 'vault'],
    pinned: true,
    age: '42m',
  },
  {
    title: 'Obsidian-compatible Markdown export',
    type: 'requirement',
    tags: ['markdown', 'yaml', 'wikilinks'],
    pinned: false,
    age: '2h',
  },
  {
    title: 'Mission Control should start mock-only',
    type: 'constraint',
    tags: ['frontend', 'phase-1'],
    pinned: true,
    age: '3h',
  },
];

export const missionProjects: MissionProject[] = [
  {
    name: 'Mission Control',
    status: 'Dashboard shell',
    progress: 38,
    next: 'Permission system',
  },
  {
    name: 'Knowledge Vault',
    status: 'Architecture defined',
    progress: 24,
    next: 'Markdown model',
  },
  {
    name: 'Local Context',
    status: 'Awareness layer',
    progress: 46,
    next: 'Desktop signals',
  },
];

export const worldSignals: WorldSignal[] = [
  { city: 'Rome', label: 'Home base', x: '50%', y: '43%', tone: 'good' },
  { city: 'New York', label: 'Market watch', x: '27%', y: '39%', tone: 'busy' },
  { city: 'Tokyo', label: 'Research watch', x: '79%', y: '44%', tone: 'watch' },
  { city: 'Sydney', label: 'Night digest', x: '83%', y: '72%', tone: 'quiet' },
];

export const terminalSignals: TerminalSignal[] = [
  {
    command: 'npm run build',
    status: 'Last check pending',
    detail: 'Frontend validation will run after this shell is in place.',
    tone: 'busy',
  },
  {
    command: 'git status --short',
    status: 'Clean checkpoint',
    detail: 'Feature branch started from siri-pre-release-1.',
    tone: 'good',
  },
  {
    command: 'shell_exec',
    status: 'Approval required',
    detail: 'Level 2 execution requests will use a confirmation gate.',
    tone: 'watch',
  },
];

export const researchItems: ResearchItem[] = [
  { title: 'Local-first AI operating layers', status: 'Queued', sources: 0, tone: 'quiet' },
  { title: 'Obsidian-style memory UX', status: 'Collecting notes', sources: 6, tone: 'busy' },
  { title: 'Tool permission models', status: 'Next pass', sources: 3, tone: 'watch' },
];

export const settingsItems = [
  { label: 'Voice control', value: 'Fn push-to-talk planned' },
  { label: 'Mode default', value: 'Focus' },
  { label: 'Data policy', value: 'Local first' },
  { label: 'Backend wiring', value: 'Deferred' },
];

export const permissionEvents: PermissionEvent[] = [
  {
    level: 'Level 0',
    label: 'Read-only',
    detail: 'Inspect files, context, memories, and status without mutation.',
    tone: 'good',
  },
  {
    level: 'Level 1',
    label: 'Safe actions',
    detail: 'Low-risk local updates and reversible UI actions.',
    tone: 'quiet',
  },
  {
    level: 'Level 2',
    label: 'Confirmed execution',
    detail: 'Shell commands and tool execution require explicit approval.',
    tone: 'watch',
  },
  {
    level: 'Level 3',
    label: 'Dangerous actions',
    detail: 'Destructive commands are hard-blocked unless explicitly confirmed.',
    tone: 'watch',
  },
];

export const quickCommands = [
  { icon: Activity, label: 'Start focus pass' },
  { icon: Brain, label: 'Capture memory' },
  { icon: TerminalSquare, label: 'Review terminal queue' },
  { icon: FileSearch, label: 'Open research lane' },
];
