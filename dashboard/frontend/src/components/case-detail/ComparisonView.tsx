import type { ParsedGraph, DiagnosticInfo } from '../../api/types';
import { Badge } from '../common/Badge';

interface ComparisonViewProps {
  parsedResponse: ParsedGraph;
  groundTruthGraph: ParsedGraph;
  diagnostic: DiagnosticInfo;
}

export function ComparisonView({
  parsedResponse,
  groundTruthGraph,
  diagnostic,
}: ComparisonViewProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Agent Prediction */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
          <h3 className="font-semibold text-slate-800">Agent Prediction</h3>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <h4 className="text-sm font-medium text-slate-600 mb-2">Root Causes</h4>
            <div className="flex flex-wrap gap-2">
              {parsedResponse.root_causes.length > 0 ? (
                parsedResponse.root_causes.map((rc, idx) => {
                  const isMatched = diagnostic.matched_services.includes(rc);
                  const isHallucinated = diagnostic.hallucinated_services.includes(rc);
                  return (
                    <Badge
                      key={idx}
                      variant={isMatched ? 'success' : isHallucinated ? 'warning' : 'default'}
                    >
                      {rc}
                      {isMatched && ' ✓'}
                      {isHallucinated && ' (hallucinated)'}
                    </Badge>
                  );
                })
              ) : (
                <span className="text-sm text-slate-400">None identified</span>
              )}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-slate-600 mb-2">
              Nodes ({parsedResponse.nodes.length})
            </h4>
            <div className="flex flex-wrap gap-2">
              {parsedResponse.nodes.map((node, idx) => (
                <Badge
                  key={idx}
                  variant={
                    node.match_status === 'matched'
                      ? 'success'
                      : node.match_status === 'hallucinated'
                      ? 'warning'
                      : 'default'
                  }
                >
                  {node.component}
                </Badge>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-slate-600 mb-2">
              Edges ({parsedResponse.edges.length})
            </h4>
            <div className="space-y-1">
              {parsedResponse.edges.length > 0 ? (
                parsedResponse.edges.map((edge, idx) => (
                  <div
                    key={idx}
                    className={`text-sm px-2 py-1 rounded ${
                      edge.match_status === 'matched'
                        ? 'bg-emerald-50 text-emerald-700'
                        : edge.match_status === 'hallucinated'
                        ? 'bg-amber-50 text-amber-700'
                        : 'bg-slate-50 text-slate-600'
                    }`}
                  >
                    {edge.source} → {edge.target}
                  </div>
                ))
              ) : (
                <span className="text-sm text-slate-400">No edges</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Ground Truth */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
          <h3 className="font-semibold text-slate-800">Ground Truth</h3>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <h4 className="text-sm font-medium text-slate-600 mb-2">Root Causes</h4>
            <div className="flex flex-wrap gap-2">
              {groundTruthGraph.root_causes.length > 0 ? (
                groundTruthGraph.root_causes.map((rc, idx) => {
                  const isMatched = diagnostic.matched_services.includes(rc);
                  const isMissed = diagnostic.missed_services.includes(rc);
                  return (
                    <Badge
                      key={idx}
                      variant={isMatched ? 'success' : isMissed ? 'error' : 'default'}
                    >
                      {rc}
                      {isMatched && ' ✓'}
                      {isMissed && ' (missed)'}
                    </Badge>
                  );
                })
              ) : (
                <span className="text-sm text-slate-400">None specified</span>
              )}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-slate-600 mb-2">
              Nodes ({groundTruthGraph.nodes.length})
            </h4>
            <div className="flex flex-wrap gap-2">
              {groundTruthGraph.nodes.map((node, idx) => (
                <Badge
                  key={idx}
                  variant={
                    node.match_status === 'matched'
                      ? 'success'
                      : node.match_status === 'missed'
                      ? 'error'
                      : 'default'
                  }
                >
                  {node.component}
                </Badge>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-slate-600 mb-2">
              Edges ({groundTruthGraph.edges.length})
            </h4>
            <div className="space-y-1">
              {groundTruthGraph.edges.length > 0 ? (
                groundTruthGraph.edges.map((edge, idx) => (
                  <div
                    key={idx}
                    className={`text-sm px-2 py-1 rounded ${
                      edge.match_status === 'matched'
                        ? 'bg-emerald-50 text-emerald-700'
                        : edge.match_status === 'missed'
                        ? 'bg-red-50 text-red-700'
                        : 'bg-slate-50 text-slate-600'
                    }`}
                  >
                    {edge.source} → {edge.target}
                  </div>
                ))
              ) : (
                <span className="text-sm text-slate-400">No edges</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-4">
        <h4 className="text-sm font-medium text-slate-600 mb-3">Legend</h4>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <Badge variant="success">Matched</Badge>
            <span className="text-sm text-slate-500">Correctly identified</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="error">Missed</Badge>
            <span className="text-sm text-slate-500">In ground truth but not predicted</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="warning">Hallucinated</Badge>
            <span className="text-sm text-slate-500">Predicted but not in ground truth</span>
          </div>
        </div>
      </div>
    </div>
  );
}
