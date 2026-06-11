import { Badge } from '../../../components/ui';
import type { ChassisComponent, ChassisTreeNode } from './chassisTypes';
import { collectManagedPorts, isLogicalInterfaceName, type ManagedInterface } from './portInventory';

export function DiscoveredElementsTree({
  tree,
  componentsById,
  managedInterfaces,
  selectedComponentId,
  onSelect,
}: {
  tree: ChassisTreeNode[];
  componentsById: Record<string, ChassisComponent>;
  managedInterfaces: ManagedInterface[];
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
}) {
  const logicalInterfaces = managedInterfaces
    .filter((iface) => isLogicalInterfaceName(iface.name))
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));

  return (
    <div className="max-h-[430px] overflow-auto rounded-lg border border-gray-200 bg-white/90 p-3 shadow dark:border-gray-700 dark:bg-gray-900/95">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Discovered elements</p>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Inventory tree</p>
        </div>
        <Badge variant="success">Synced</Badge>
      </div>
      <div className="space-y-1 text-sm">
        {tree.map((node) => (
          <TreeNodeRow
            key={node.id}
            node={node}
            depth={0}
            componentsById={componentsById}
            selectedComponentId={selectedComponentId}
            onSelect={onSelect}
          />
        ))}
        {logicalInterfaces.length > 0 && (
          <div className="pt-2">
            <div className="px-2 py-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Logical interfaces</div>
            {logicalInterfaces.map((iface) => (
              <div
                key={iface.id}
                className="grid grid-cols-[1fr_auto] gap-2 rounded px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300"
                style={{ paddingLeft: 22 }}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{iface.name}</span>
                  <span className="block truncate text-xs text-gray-500 dark:text-gray-400">{iface.description ?? iface.alias ?? 'logical'}</span>
                </span>
                <span className="font-mono text-xs text-gray-500 dark:text-gray-400">{iface.if_index ?? '-'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TreeNodeRow({
  node,
  depth,
  componentsById,
  selectedComponentId,
  onSelect,
}: {
  node: ChassisTreeNode;
  depth: number;
  componentsById: Record<string, ChassisComponent>;
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
}) {
  const component = componentsById[node.componentId];
  const active = selectedComponentId === node.componentId;
  const portCount = collectManagedPorts(component, componentsById).length;

  return (
    <div>
      <button
        type="button"
        onClick={() => onSelect(node.componentId)}
        className={`grid w-full grid-cols-[1fr_auto] gap-2 rounded px-2 py-2 text-left transition ${
          active ? 'bg-cisco-blue text-white' : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
        }`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        <span className="min-w-0">
          <span className="block truncate font-medium">{node.label}</span>
          <span className={`block truncate text-xs ${active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
            {component?.typeId ?? component?.type ?? node.type}
          </span>
        </span>
        <span className="flex flex-col items-end gap-1 text-xs">
          {component?.operStatus && <span>{component.operStatus}</span>}
          {portCount > 0 && <span className={active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}>{portCount} ports</span>}
        </span>
      </button>
      {node.children.map((child) => (
        <TreeNodeRow
          key={child.id}
          node={child}
          depth={depth + 1}
          componentsById={componentsById}
          selectedComponentId={selectedComponentId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
