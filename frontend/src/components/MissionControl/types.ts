import type { LucideIcon } from 'lucide-react';

export type MissionSectionId =
  | 'home'
  | 'today'
  | 'world-map'
  | 'tasks'
  | 'agents'
  | 'memory'
  | 'projects'
  | 'terminal'
  | 'research'
  | 'learning'
  | 'mcp'
  | 'release'
  | 'settings'
  | 'personalization'
  | 'permissions'
  | 'autonomy';

export type StatusTone = 'good' | 'watch' | 'busy' | 'quiet';

export type MissionSection = {
  id: MissionSectionId;
  label: string;
  icon: LucideIcon;
};

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
  state: 'Pinned' | 'Running' | 'Review' | 'Queued' | 'Done';
  due: string;
  tone: StatusTone;
};

export type MissionAgent = {
  name: string;
  role: string;
  status: string;
  load: number;
  tone: StatusTone;
};

export type MissionMemory = {
  title: string;
  type: string;
  tags: string[];
  pinned: boolean;
  age: string;
};

export type MissionProject = {
  name: string;
  status: string;
  progress: number;
  next: string;
};

export type WorldSignal = {
  city: string;
  label: string;
  x: string;
  y: string;
  tone: StatusTone;
};

export type TerminalSignal = {
  command: string;
  status: string;
  detail: string;
  tone: StatusTone;
};

export type ResearchItem = {
  title: string;
  status: string;
  sources: number;
  tone: StatusTone;
};

export type PermissionEvent = {
  level: 'Level 0' | 'Level 1' | 'Level 2' | 'Level 3';
  label: string;
  detail: string;
  tone: StatusTone;
};
