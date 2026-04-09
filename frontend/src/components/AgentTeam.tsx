'use client';
import { AgentName, AgentStatus } from '@/types';

const AGENT_CONFIG: Record<AgentName, { color: string; bg: string; icon: string; role: string }> = {
  Planner:     { color: 'text-purple-400',  bg: 'bg-purple-500/10 border-purple-500/30',  icon: '🧠', role: 'Project Planner' },
  Developer:   { color: 'text-cyan-400',    bg: 'bg-cyan-500/10 border-cyan-500/30',      icon: '💻', role: 'Code Developer' },
  Analyzer:    { color: 'text-green-400',   bg: 'bg-green-500/10 border-green-500/30',    icon: '🔍', role: 'Code Analyzer' },
  Fixer:       { color: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/30',    icon: '🔧', role: 'Bug Fixer' },
  Runner:      { color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/30',        icon: '🚀', role: 'App Runner' },
  Orchestrator:{ color: 'text-slate-400',   bg: 'bg-slate-500/10 border-slate-500/30',    icon: '⚙️', role: 'Orchestrator' }
};

const AGENT_ORDER: AgentName[] = ['Planner', 'Developer', 'Analyzer', 'Fixer', 'Runner'];

interface AgentTeamProps {
  agents: AgentStatus[];
  currentAgent: string;
  streamingToken: string;
}

export function AgentTeam({ agents, currentAgent, streamingToken }: AgentTeamProps) {
  const getAgent = (name: AgentName): AgentStatus => {
    return agents.find(a => a.name === name) || { name, status: 'idle' };
  };

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-[#1a1a2e] overflow-x-auto">
      <span className="text-xs text-slate-500 shrink-0 font-medium">AI Team</span>
      <div className="flex gap-2">
        {AGENT_ORDER.map((name) => {
          const agent = getAgent(name);
          const cfg = AGENT_CONFIG[name];
          const isActive = agent.status === 'working' || currentAgent === name;
          const isDone = agent.status === 'done';
          const isError = agent.status === 'error';

          return (
            <div
              key={name}
              className={`
                flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-all duration-300
                ${isActive ? cfg.bg + ' ' + cfg.color + ' scale-105' : 'bg-[#0f0f1a] border-[#1a1a2e] text-slate-500'}
                ${isDone ? 'border-green-500/20 text-green-400' : ''}
                ${isError ? 'border-red-500/20 text-red-400' : ''}
              `}
            >
              <span className={isActive ? 'animate-pulse' : ''}>{cfg.icon}</span>
              <div>
                <div className="font-medium leading-tight">{name}</div>
                <div className={`text-[10px] leading-tight ${isActive ? 'opacity-80' : 'text-slate-600'}`}>
                  {cfg.role}
                </div>
              </div>
              {isActive && (
                <div className="flex gap-0.5 ml-1">
                  {[0, 1, 2].map(i => (
                    <div
                      key={i}
                      className={`w-1 h-1 rounded-full ${cfg.color.replace('text-', 'bg-')}`}
                      style={{ animation: `bounce 1.4s ease-in-out ${i * 0.16}s infinite` }}
                    />
                  ))}
                </div>
              )}
              {isDone && <span className="text-green-400">✓</span>}
              {isError && <span className="text-red-400">✗</span>}
            </div>
          );
        })}
      </div>

      {/* Live streaming indicator */}
      {streamingToken && (
        <div className="ml-auto shrink-0 flex items-center gap-2 text-xs text-purple-400">
          <div className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
          <span>Generating...</span>
        </div>
      )}
    </div>
  );
}
