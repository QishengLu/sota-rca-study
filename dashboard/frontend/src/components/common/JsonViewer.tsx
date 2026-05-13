import { useState } from 'react';

interface JsonViewerProps {
  data: unknown;
  collapsed?: boolean;
  maxHeight?: string;
}

export function JsonViewer({ data, collapsed = true, maxHeight = '400px' }: JsonViewerProps) {
  const [isExpanded, setIsExpanded] = useState(!collapsed);

  const jsonString = JSON.stringify(data, null, 2);
  const lines = jsonString.split('\n');
  const isLong = lines.length > 10;

  return (
    <div className="relative">
      {isLong && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="absolute top-2 right-2 px-2 py-1 text-xs bg-slate-700 text-slate-300 rounded hover:bg-slate-600 z-10"
        >
          {isExpanded ? 'Collapse' : 'Expand'}
        </button>
      )}
      <pre
        className="bg-slate-800 text-slate-200 p-4 rounded-lg overflow-auto text-sm"
        style={{ maxHeight: isExpanded ? maxHeight : '150px' }}
      >
        <code>{jsonString}</code>
      </pre>
    </div>
  );
}
