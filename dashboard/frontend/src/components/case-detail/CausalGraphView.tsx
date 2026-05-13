import { useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MarkerType,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import type { ParsedGraph, DiagnosticInfo, GraphEdge as GraphEdgeType, GraphNode as GraphNodeType } from '../../api/types';

interface CausalGraphViewProps {
  parsedResponse: ParsedGraph;
  groundTruthGraph: ParsedGraph;
  diagnostic: DiagnosticInfo;
  componentToService?: Record<string, string>;
}

// Colors for prediction graph (left)
const predColors = {
  matched: '#10b981',      // Green - correctly predicted
  hallucinated: '#ef4444', // Red - false positive (not in GT)
  root_cause: '#8b5cf6',   // Purple - root cause
  default: '#64748b',
};

// Colors for ground truth graph (right)
const gtColors = {
  matched: '#10b981',      // Green - correctly predicted by model
  missed: '#9ca3af',       // Gray - missed by model
  default: '#f59e0b',      // Yellow/Amber - GT nodes
  root_cause: '#8b5cf6',   // Purple - root cause
};

function sanitizeId(id: string, prefix: string): string {
  return `${prefix}-${id.replace(/[^a-zA-Z0-9_-]/g, '_')}`;
}

function normalizeServiceName(name: string): string {
  return name.toLowerCase().replace(/^ts-/, '').replace(/-/g, '');
}

function getServiceName(component: string, componentToService: Record<string, string>): string {
  if (componentToService[component]) {
    return componentToService[component];
  }
  if (component.startsWith('service|')) {
    return component.substring(8);
  }
  if (component.startsWith('span|')) {
    const spanName = component.substring(5);
    const httpMatch = spanName.match(/https?:\/\/(ts-[\w-]+):/);
    if (httpMatch) return httpMatch[1];
  }
  return component;
}

function aggregateToServiceLevel(
  nodes: GraphNodeType[],
  edges: GraphEdgeType[],
  rootCauses: string[],
  componentToService: Record<string, string>
) {
  const services = new Set<string>();
  const serviceEdges: Array<{ source: string; target: string }> = [];
  const serviceRootCauses = new Set<string>();
  const localC2S = new Map<string, string>();
  const seenEdges = new Set<string>();

  // First, build component to service mapping from nodes
  for (const node of nodes) {
    const svc = getServiceName(node.component, componentToService);
    localC2S.set(node.component, svc);
    services.add(svc);
  }

  // Process edges and ensure all referenced services are included
  for (const edge of edges) {
    const src = localC2S.get(edge.source) || getServiceName(edge.source, componentToService);
    const tgt = localC2S.get(edge.target) || getServiceName(edge.target, componentToService);

    // Add services from edges (in case they're not in nodes)
    services.add(src);
    services.add(tgt);

    if (src !== tgt) {
      const key = `${src}->${tgt}`;
      if (!seenEdges.has(key)) {
        seenEdges.add(key);
        serviceEdges.push({ source: src, target: tgt });
      }
    }
  }

  for (const rc of rootCauses) {
    serviceRootCauses.add(localC2S.get(rc) || getServiceName(rc, componentToService));
  }

  return { services, edges: serviceEdges, rootCauses: serviceRootCauses };
}

// Simple hierarchical layout based on topological sort
function calculateLayout(
  nodeIds: string[],
  edges: Array<{ source: string; target: string }>
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (nodeIds.length === 0) return positions;

  const nodeSet = new Set(nodeIds);
  const edgeList = edges.filter(e => nodeSet.has(e.source) && nodeSet.has(e.target));

  // Build adjacency
  const outEdges = new Map<string, string[]>();
  const inDegree = new Map<string, number>();

  nodeIds.forEach(id => {
    outEdges.set(id, []);
    inDegree.set(id, 0);
  });

  for (const e of edgeList) {
    outEdges.get(e.source)!.push(e.target);
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
  }

  // Kahn's algorithm for level assignment
  const levels = new Map<string, number>();
  const queue: string[] = [];

  for (const id of nodeIds) {
    if (inDegree.get(id) === 0) {
      queue.push(id);
      levels.set(id, 0);
    }
  }

  // Fallback if no root nodes
  if (queue.length === 0) {
    let minDegree = Infinity;
    for (const id of nodeIds) {
      const deg = inDegree.get(id) || 0;
      if (deg < minDegree) minDegree = deg;
    }
    for (const id of nodeIds) {
      if ((inDegree.get(id) || 0) === minDegree) {
        queue.push(id);
        levels.set(id, 0);
      }
    }
  }

  const processed = new Set<string>();
  while (queue.length > 0) {
    const curr = queue.shift()!;
    if (processed.has(curr)) continue;
    processed.add(curr);

    const currLevel = levels.get(curr)!;
    for (const next of outEdges.get(curr) || []) {
      const newLevel = currLevel + 1;
      const existingLevel = levels.get(next);
      if (existingLevel === undefined || newLevel > existingLevel) {
        levels.set(next, newLevel);
      }
      const newDegree = (inDegree.get(next) || 1) - 1;
      inDegree.set(next, newDegree);
      if (newDegree <= 0 && !processed.has(next)) {
        queue.push(next);
      }
    }
  }

  // Handle disconnected nodes
  for (const id of nodeIds) {
    if (!levels.has(id)) {
      levels.set(id, 0);
    }
  }

  // Position nodes
  const levelHeight = 120;
  const nodeWidth = 180;
  const levelGroups = new Map<number, string[]>();

  for (const [id, level] of levels) {
    if (!levelGroups.has(level)) levelGroups.set(level, []);
    levelGroups.get(level)!.push(id);
  }

  for (const [level, nodesAtLevel] of levelGroups) {
    const totalWidth = nodesAtLevel.length * nodeWidth;
    const startX = (400 - totalWidth) / 2 + nodeWidth / 2;

    nodesAtLevel.forEach((id, idx) => {
      positions.set(id, {
        x: startX + idx * nodeWidth,
        y: level * levelHeight + 50,
      });
    });
  }

  return positions;
}

// Single graph component for reuse
function SingleGraph({
  nodes,
  edges,
  title,
}: {
  nodes: Node[];
  edges: Edge[];
  title: string;
}) {
  const [flowNodes, , onNodesChange] = useNodesState(nodes);
  const [flowEdges, , onEdgesChange] = useEdgesState(edges);

  return (
    <div className="flex-1 flex flex-col">
      <div className="text-sm font-medium text-slate-700 mb-2 px-2">{title}</div>
      <div className="flex-1 bg-slate-50 rounded-lg border overflow-hidden min-h-[400px]">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={true}
          nodesConnectable={false}
          minZoom={0.3}
          maxZoom={2}
        >
          <Background color="#e2e8f0" gap={16} />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}

export function CausalGraphView({
  parsedResponse,
  groundTruthGraph,
  diagnostic,
  componentToService = {},
}: CausalGraphViewProps) {
  // Process data for both graphs
  const { predGraph, gtGraph, stats } = useMemo(() => {
    const pred = aggregateToServiceLevel(
      parsedResponse.nodes, parsedResponse.edges, parsedResponse.root_causes, componentToService
    );
    const gt = aggregateToServiceLevel(
      groundTruthGraph.nodes, groundTruthGraph.edges, groundTruthGraph.root_causes, componentToService
    );

    // Normalize diagnostic info for comparison
    const matchedNorm = new Set(diagnostic.matched_services.map(normalizeServiceName));
    const hallucinatedNorm = new Set(diagnostic.hallucinated_services.map(normalizeServiceName));
    const missedNorm = new Set(diagnostic.missed_services.map(normalizeServiceName));

    const matchedEdgesNorm = new Set(
      diagnostic.matched_service_edges.map(e => `${normalizeServiceName(e[0])}->${normalizeServiceName(e[1])}`)
    );
    const hallucinatedEdgesNorm = new Set(
      diagnostic.hallucinated_service_edges.map(e => `${normalizeServiceName(e[0])}->${normalizeServiceName(e[1])}`)
    );
    const missedEdgesNorm = new Set(
      diagnostic.missed_service_edges.map(e => `${normalizeServiceName(e[0])}->${normalizeServiceName(e[1])}`)
    );

    // Build prediction graph (left side)
    const predPositions = calculateLayout(Array.from(pred.services), pred.edges);

    const predNodes: Node[] = Array.from(pred.services).map(svc => {
      const norm = normalizeServiceName(svc);
      const isRootCause = pred.rootCauses.has(svc);
      const isMatched = matchedNorm.has(norm);
      const isHallucinated = hallucinatedNorm.has(norm);

      let color = predColors.default;
      if (isRootCause) color = predColors.root_cause;
      else if (isMatched) color = predColors.matched;
      else if (isHallucinated) color = predColors.hallucinated;

      const pos = predPositions.get(svc) || { x: 0, y: 0 };

      return {
        id: sanitizeId(svc, 'pred'),
        data: {
          label: (
            <div className="text-center">
              <div className="text-xs">{svc}</div>
              {isRootCause && <div className="text-[9px] opacity-80">(Root Cause)</div>}
            </div>
          ),
        },
        position: pos,
        style: {
          background: color,
          color: 'white',
          border: isRootCause ? '2px solid #5b21b6' : 'none',
          borderRadius: '8px',
          padding: '8px 12px',
          fontSize: '11px',
          fontWeight: 500,
          boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
          minWidth: '100px',
        },
      };
    });

    const predEdges: Edge[] = pred.edges.map((edge, idx) => {
      const normKey = `${normalizeServiceName(edge.source)}->${normalizeServiceName(edge.target)}`;
      const isMatched = matchedEdgesNorm.has(normKey);
      const isHallucinated = hallucinatedEdgesNorm.has(normKey);

      let color = predColors.default;
      if (isMatched) color = predColors.matched;
      else if (isHallucinated) color = predColors.hallucinated;

      return {
        id: `pred-e-${idx}`,
        source: sanitizeId(edge.source, 'pred'),
        target: sanitizeId(edge.target, 'pred'),
        type: 'smoothstep',
        style: { stroke: color, strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
      };
    });

    // Build ground truth graph (right side)
    const gtPositions = calculateLayout(Array.from(gt.services), gt.edges);

    const gtNodes: Node[] = Array.from(gt.services).map(svc => {
      const norm = normalizeServiceName(svc);
      const isRootCause = gt.rootCauses.has(svc);
      const isMatched = matchedNorm.has(norm);
      const isMissed = missedNorm.has(norm);

      let color = gtColors.default;
      if (isRootCause) color = gtColors.root_cause;
      else if (isMatched) color = gtColors.matched;
      else if (isMissed) color = gtColors.missed;

      const pos = gtPositions.get(svc) || { x: 0, y: 0 };

      return {
        id: sanitizeId(svc, 'gt'),
        data: {
          label: (
            <div className="text-center">
              <div className="text-xs">{svc}</div>
              {isRootCause && <div className="text-[9px] opacity-80">(Root Cause)</div>}
            </div>
          ),
        },
        position: pos,
        style: {
          background: color,
          color: 'white',
          border: isRootCause ? '2px solid #5b21b6' : 'none',
          borderRadius: '8px',
          padding: '8px 12px',
          fontSize: '11px',
          fontWeight: 500,
          boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
          minWidth: '100px',
        },
      };
    });

    const gtEdges: Edge[] = gt.edges.map((edge, idx) => {
      const normKey = `${normalizeServiceName(edge.source)}->${normalizeServiceName(edge.target)}`;
      const isMatched = matchedEdgesNorm.has(normKey);
      const isMissed = missedEdgesNorm.has(normKey);

      let color = gtColors.default;
      if (isMatched) color = gtColors.matched;
      else if (isMissed) color = gtColors.missed;

      return {
        id: `gt-e-${idx}`,
        source: sanitizeId(edge.source, 'gt'),
        target: sanitizeId(edge.target, 'gt'),
        type: 'smoothstep',
        style: {
          stroke: color,
          strokeWidth: 2,
          strokeDasharray: isMissed ? '4,3' : undefined,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
      };
    });

    return {
      predGraph: { nodes: predNodes, edges: predEdges },
      gtGraph: { nodes: gtNodes, edges: gtEdges },
      stats: {
        predNodes: pred.services.size,
        gtNodes: gt.services.size,
        matched: matchedNorm.size,
        hallucinated: hallucinatedNorm.size,
        missed: missedNorm.size,
      },
    };
  }, [parsedResponse, groundTruthGraph, diagnostic, componentToService]);

  if (predGraph.nodes.length === 0 && gtGraph.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 bg-slate-50 rounded-lg border">
        <div className="text-slate-500">No graph data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-3 py-2 bg-white rounded-lg border text-xs">
        <div className="flex items-center gap-4">
          <span className="font-medium text-slate-600">Legend:</span>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded" style={{ background: predColors.matched }} />
            <span>Matched ({stats.matched})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded" style={{ background: predColors.hallucinated }} />
            <span>Hallucinated ({stats.hallucinated})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded" style={{ background: gtColors.missed }} />
            <span>Missed ({stats.missed})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded" style={{ background: gtColors.default }} />
            <span>Ground Truth</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded border-2 border-purple-700" style={{ background: predColors.root_cause }} />
            <span>Root Cause</span>
          </div>
        </div>
      </div>

      {/* Two graphs side by side */}
      <div className="flex gap-4 h-[500px]">
        <SingleGraph
          nodes={predGraph.nodes}
          edges={predGraph.edges}
          title={`Model Prediction (${stats.predNodes} services)`}
        />
        <SingleGraph
          nodes={gtGraph.nodes}
          edges={gtGraph.edges}
          title={`Ground Truth (${stats.gtNodes} services)`}
        />
      </div>
    </div>
  );
}

