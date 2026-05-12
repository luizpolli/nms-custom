import { useCallback, useEffect } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { DeviceNode, type DeviceNodeData } from './DeviceNode';
import { applyDagreLayout } from '../dagre-layout';

export interface ApiNode {
  id: string;
  label: string;
  role?: string;
  vendor?: string;
  position?: { x: number; y: number };
}

export interface ApiLink {
  source: string;
  target: string;
  source_iface?: string;
  target_iface?: string;
}

interface Props {
  nodes: ApiNode[];
  links: ApiLink[];
}

const nodeTypes = { deviceNode: DeviceNode };

function buildNodes(apiNodes: ApiNode[]): Node<DeviceNodeData>[] {
  return apiNodes.map((n) => ({
    id: n.id,
    type: 'deviceNode',
    position: n.position ?? { x: 0, y: 0 },
    data: { label: n.label, role: n.role, vendor: n.vendor },
  }));
}

function buildEdges(links: ApiLink[]): Edge[] {
  return links.map((l, i) => {
    const label = [l.source_iface, l.target_iface].filter(Boolean).join(' ↔ ');
    return {
      id: `e-${i}-${l.source}-${l.target}`,
      source: l.source,
      target: l.target,
      label: label || undefined,
      labelStyle: { fontSize: 10 },
      markerEnd: { type: MarkerType.ArrowClosed },
    };
  });
}

export function TopologyGraph({ nodes: apiNodes, links }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<DeviceNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    const rawNodes = buildNodes(apiNodes);
    const rawEdges = buildEdges(links);
    const hasPositions = apiNodes.every((n) => n.position);
    const layoutNodes = hasPositions ? rawNodes : applyDagreLayout(rawNodes, rawEdges);
    setNodes(layoutNodes);
    setEdges(rawEdges);
  }, [apiNodes, links, setNodes, setEdges]);

  const miniMapNodeColor = useCallback((node: Node<DeviceNodeData>) => {
    const vendor = (node.data.vendor ?? '').toLowerCase();
    const colors: Record<string, string> = {
      cisco: '#3b82f6',
      juniper: '#22c55e',
      arista: '#14b8a6',
    };
    return colors[vendor] ?? '#9ca3af';
  }, []);

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
      >
        <Background gap={20} size={1} />
        <Controls />
        <MiniMap nodeColor={miniMapNodeColor} zoomable pannable />
      </ReactFlow>
    </div>
  );
}
