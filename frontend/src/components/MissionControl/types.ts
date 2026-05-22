import type { LucideIcon } from 'lucide-react';

export type MissionSectionId =
  | 'home'
  | 'today'
  | 'world-map'
  | 'daily-briefing'
  | 'important-events'
  | 'tasks'
  | 'agents'
  | 'memory'
  | 'projects'
  | 'sessions'
  | 'desktop'
  | 'notifications'
  | 'engineering'
  | 'coding'
  | 'repo'
  | 'voice'
  | 'vision'
  | 'terminal'
  | 'workflows'
  | 'research'
  | 'learning'
  | 'mcp'
  | 'release'
  | 'settings'
  | 'personalization'
  | 'permissions'
  | 'autonomy';

export type MissionSection = {
  id: MissionSectionId;
  label: string;
  icon: LucideIcon;
};

export type StatusTone = 'good' | 'watch' | 'busy' | 'quiet';

export type MissionMetric = {
  label: string;
  value: string;
  detail: string;
  tone: StatusTone;
};

export type MissionFeedItem = {
  time: string;
  title: string;
  detail: string;
  tone: StatusTone;
};

export type MissionTask = {
  title: string;
  owner: string;
  state: 'Queued' | 'Running' | 'Review' | 'Done';
  due: string;
};

export type MissionAgent = {
  name: string;
  role: string;
  status: string;
  load: number;
};

export type MissionProject = {
  name: string;
  status: string;
  progress: number;
  next: string;
};

export type MissionMemory = {
  id: string;
  content: string;
  memory_type: string;
  tags: string[];
  pinned: boolean;
  created_at: string;
  source?: {
    title: string;
    url: string;
  } | null;
};

export type PermissionEvent = {
  tool: string;
  action: 'Allowed' | 'Blocked' | 'Needs approval';
  source: string;
  time: string;
  reason?: string;
};

export type ApprovalRecord = {
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
};
