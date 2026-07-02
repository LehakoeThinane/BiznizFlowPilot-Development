"use client";

import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import "@xyflow/react/dist/base.css";
import type { OrgChartNode } from "@/types/api";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 76;

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}

type OrgFlowNode = Node<OrgChartNode & Record<string, unknown>>;

function EmployeeNode({ data }: NodeProps<OrgFlowNode>) {
  return (
    <div
      className={`flex w-[220px] items-center gap-3 rounded-xl border border-outline-variant bg-[#0f1c33] px-3 py-2.5 shadow-lg ${
        data.is_active ? "" : "opacity-50"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-blue-500" />
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
        {initials(data.full_name)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-white">{data.full_name}</p>
        <p className="truncate text-xs text-slate-500">
          {data.position ?? "—"}
          {data.department_name ? ` · ${data.department_name}` : ""}
        </p>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-blue-500" />
    </div>
  );
}

const nodeTypes = { employee: EmployeeNode };

function layout(nodes: OrgChartNode[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 70 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  const edges: Edge[] = [];
  for (const n of nodes) {
    if (n.manager_id && nodes.some((m) => m.id === n.manager_id)) {
      g.setEdge(n.manager_id, n.id);
      edges.push({
        id: `${n.manager_id}->${n.id}`,
        source: n.manager_id,
        target: n.id,
        type: "smoothstep",
        style: { stroke: "#3b82f6", strokeWidth: 1.5 },
      });
    }
  }
  dagre.layout(g);

  const flowNodes: Node[] = nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: "employee",
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: n as unknown as Record<string, unknown>,
      draggable: false,
      connectable: false,
    };
  });

  return { nodes: flowNodes, edges };
}

export function OrgChart({ nodes }: { nodes: OrgChartNode[] }) {
  const { nodes: flowNodes, edges: flowEdges } = useMemo(() => layout(nodes), [nodes]);

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        No employees yet — add employees to see the org chart.
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#334155" gap={20} />
        <Controls showInteractive={false} className="[&_button]:!bg-[#0f1c33] [&_button]:!border-outline-variant [&_button]:!text-slate-300" />
      </ReactFlow>
    </ReactFlowProvider>
  );
}
