import { describe, expect, it } from 'vitest';
import type { ChassisComponent, ChassisViewModel } from './chassisTypes';
import {
  buildPortStatusByComponentId,
  classifyPortStatus,
  type ManagedInterface,
} from './portInventory';

function makeComponent(overrides: Partial<ChassisComponent> & { id: string }): ChassisComponent {
  return {
    name: overrides.id,
    displayName: overrides.id,
    type: 'port',
    ports: [],
    childIds: [],
    ...overrides,
  };
}

function makeModel(components: ChassisComponent[]): ChassisViewModel {
  return {
    schemaVersion: 'nms.chassisView.v1',
    generatedAt: '2026-01-01T00:00:00Z',
    deviceId: 'device-1',
    profileId: 'Cisco_NCS55A1',
    platform: 'NCS-55A1',
    views: [],
    tree: [],
    componentsById: Object.fromEntries(components.map((c) => [c.id, c])),
    physicalIndexToComponentId: {},
  };
}

function makeInterface(overrides: Partial<ManagedInterface> & { id: string; name: string }): ManagedInterface {
  return { ...overrides };
}

describe('classifyPortStatus', () => {
  it('returns admin-down when admin status is down regardless of oper status', () => {
    expect(classifyPortStatus('down', 'down')).toBe('admin-down');
    expect(classifyPortStatus('Down', 'up')).toBe('admin-down');
  });

  it('returns up when oper status is up', () => {
    expect(classifyPortStatus('up', 'up')).toBe('up');
    expect(classifyPortStatus(null, 'UP')).toBe('up');
  });

  it('returns down for oper down / lowerLayerDown / dormant with admin up', () => {
    expect(classifyPortStatus('up', 'down')).toBe('down');
    expect(classifyPortStatus('up', 'lowerLayerDown')).toBe('down');
    expect(classifyPortStatus('up', 'dormant')).toBe('down');
  });

  it('returns null for unknown or missing statuses', () => {
    expect(classifyPortStatus(null, null)).toBeNull();
    expect(classifyPortStatus('up', 'notPresent')).toBeNull();
    expect(classifyPortStatus('', '')).toBeNull();
  });
});

describe('buildPortStatusByComponentId', () => {
  it('maps port components to interface status by normalized name', () => {
    const model = makeModel([
      makeComponent({ id: 'port-1', name: 'TenGigE0/0/0/0', displayName: 'TenGigE0/0/0/0' }),
      makeComponent({ id: 'port-2', name: 'TenGigE0/0/0/1', displayName: 'TenGigE0/0/0/1' }),
      makeComponent({ id: 'chassis-1', name: 'Chassis', displayName: 'Chassis', type: 'chassis' }),
    ]);
    const interfaces = [
      makeInterface({ id: 'if-1', name: 'TenGigE0/0/0/0', admin_status: 'up', oper_status: 'up' }),
      makeInterface({ id: 'if-2', name: 'TenGigE0/0/0/1', admin_status: 'up', oper_status: 'down' }),
    ];

    const result = buildPortStatusByComponentId(model, interfaces);

    expect(result['port-1']).toMatchObject({ status: 'up', interfaceName: 'TenGigE0/0/0/0' });
    expect(result['port-2']).toMatchObject({ status: 'down', interfaceName: 'TenGigE0/0/0/1' });
    expect(result['chassis-1']).toBeUndefined();
  });

  it('matches IOS XE abbreviated names against long interface names', () => {
    const model = makeModel([
      makeComponent({ id: 'port-gi', name: 'Gi0/0/1', displayName: 'Gi0/0/1' }),
    ]);
    const interfaces = [
      makeInterface({ id: 'if-1', name: 'GigabitEthernet0/0/1', admin_status: 'down', oper_status: 'down' }),
    ];

    const result = buildPortStatusByComponentId(model, interfaces);

    expect(result['port-gi']).toMatchObject({ status: 'admin-down', interfaceName: 'GigabitEthernet0/0/1' });
  });

  it('skips components without a matching interface or with unknown status', () => {
    const model = makeModel([
      makeComponent({ id: 'port-1', name: 'TenGigE0/0/0/0', displayName: 'TenGigE0/0/0/0' }),
      makeComponent({ id: 'port-2', name: 'TenGigE0/0/0/9', displayName: 'TenGigE0/0/0/9' }),
    ]);
    const interfaces = [
      makeInterface({ id: 'if-1', name: 'TenGigE0/0/0/0', admin_status: 'up', oper_status: 'notPresent' }),
    ];

    const result = buildPortStatusByComponentId(model, interfaces);

    expect(result).toEqual({});
  });

  it('returns empty map when there are no interfaces', () => {
    const model = makeModel([
      makeComponent({ id: 'port-1', name: 'TenGigE0/0/0/0', displayName: 'TenGigE0/0/0/0' }),
    ]);

    expect(buildPortStatusByComponentId(model, [])).toEqual({});
  });
});
