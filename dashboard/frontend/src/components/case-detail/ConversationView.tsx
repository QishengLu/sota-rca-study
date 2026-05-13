import { useState } from 'react';
import type { TrajectoryItem } from '../../api/types';
import { JsonViewer } from '../common/JsonViewer';
import { clsx } from 'clsx';

interface ConversationViewProps {
  trajectories: TrajectoryItem[];
}

export function ConversationView({ trajectories }: ConversationViewProps) {
  if (trajectories.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500">
        No conversation history available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {trajectories.map((item, index) => (
        <MessageItem key={index} item={item} />
      ))}
    </div>
  );
}

function MessageItem({ item }: { item: TrajectoryItem }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const roleStyles: Record<string, string> = {
    user: 'bg-blue-50 border-blue-200',
    assistant: 'bg-slate-50 border-slate-200',
    tool: 'bg-amber-50 border-amber-200',
    system: 'bg-purple-50 border-purple-200',
  };

  const roleLabels: Record<string, string> = {
    user: 'User',
    assistant: 'Assistant',
    tool: 'Tool Result',
    system: 'System',
  };

  const hasToolCalls = item.tool_calls && item.tool_calls.length > 0;
  const isLongContent = item.content && item.content.length > 500;

  return (
    <div className={clsx('rounded-lg border p-4', roleStyles[item.role] || roleStyles.assistant)}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-700">
            {roleLabels[item.role] || item.role}
          </span>
          {item.name && (
            <span className="text-xs text-slate-500 bg-white px-2 py-0.5 rounded">
              {item.name}
            </span>
          )}
          {item.tool_call_id && (
            <span className="text-xs text-slate-400 font-mono">
              {item.tool_call_id.slice(0, 12)}...
            </span>
          )}
        </div>
        {(isLongContent || hasToolCalls) && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs text-primary-600 hover:text-primary-700"
          >
            {isExpanded ? 'Collapse' : 'Expand'}
          </button>
        )}
      </div>

      {item.content && (
        <div className="text-sm text-slate-700 whitespace-pre-wrap">
          {isLongContent && !isExpanded ? (
            <>
              {item.content.slice(0, 500)}
              <span className="text-slate-400">... (truncated)</span>
            </>
          ) : (
            item.content
          )}
        </div>
      )}

      {hasToolCalls && (
        <div className="mt-3 space-y-2">
          {item.tool_calls!.map((toolCall, idx) => (
            <ToolCallCard
              key={idx}
              toolCall={toolCall}
              isExpanded={isExpanded}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface ToolCallCardProps {
  toolCall: {
    id?: string;
    type?: string;
    function?: {
      name: string;
      arguments: string;
    };
  };
  isExpanded: boolean;
}

function ToolCallCard({ toolCall, isExpanded }: ToolCallCardProps) {
  const [showArgs, setShowArgs] = useState(false);

  const funcName = toolCall.function?.name || 'unknown';
  const argsStr = toolCall.function?.arguments || '{}';

  let parsedArgs: unknown;
  try {
    parsedArgs = JSON.parse(argsStr);
  } catch {
    parsedArgs = argsStr;
  }

  return (
    <div className="bg-white rounded border border-slate-200 overflow-hidden">
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-slate-50"
        onClick={() => setShowArgs(!showArgs)}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-600">
            {funcName}
          </span>
          {toolCall.id && (
            <span className="text-xs text-slate-400">
              {toolCall.id.slice(0, 8)}
            </span>
          )}
        </div>
        <span className="text-xs text-slate-400">
          {showArgs || isExpanded ? '▼' : '▶'}
        </span>
      </div>

      {(showArgs || isExpanded) && (
        <div className="border-t border-slate-200 p-2">
          <JsonViewer data={parsedArgs} collapsed={false} maxHeight="300px" />
        </div>
      )}
    </div>
  );
}
