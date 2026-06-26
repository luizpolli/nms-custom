export type ChassisComponentPort = {
  id: string;
  name?: string;
  portId?: number | string;
};

export type ChassisComponent = {
  id: string;
  sourceId?: number | string;
  parentId?: string | null;
  name: string;
  displayName: string;
  description?: string;
  type: string;
  typeId?: string;
  physicalIndex?: number | string;
  containedPhysicalIndex?: number | string;
  operStatus?: string;
  serviceState?: number | string;
  serialNumber?: string;
  hardwareVersion?: string;
  manufacturer?: string;
  isFRUable?: boolean;
  source?: {
    type?: string;
    physicalIndex?: number | string;
  };
  ports: ChassisComponentPort[];
  childIds: string[];
};

export type ChassisTreeNode = {
  id: string;
  label: string;
  type: string;
  typeId?: string;
  physicalIndex?: number | string;
  componentId: string;
  children: ChassisTreeNode[];
};

export type ChassisHotspot = {
  id: string;
  slotKey: string;
  label: string;
  asset?: {
    typeId: string;
    image: string;
    sourceImage?: string;
  };
  inventoryId?: string | null;
  physicalIndex?: number | string;
  empty: boolean;
  bounds: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  metadata?: {
    alias?: number | string;
    fillerTypeId?: string;
    sourceName?: string;
    sourceTypeId?: string;
    modelName?: string;
    modelTypeId?: string;
    /** Decorative background art (e.g. a line-card faceplate); rendered as a
     *  SlotAsset only — no selectable/highlightable hotspot button. */
    kind?: string;
  };
};

export type ChassisViewImage = {
  id: string;
  label: string;
  image: string;
  sourceImage?: string;
  width: number;
  height: number;
  sourceWidth?: number;
  sourceHeight?: number;
  hotspots: ChassisHotspot[];
};

export type ComponentAlarmInfo = {
  maxSeverity: 'critical' | 'major' | 'minor' | 'warning' | 'info';
  count: number;
};

export type AlarmSummary = {
  critical: number;
  major: number;
  minor: number;
  warning: number;
  info: number;
  total: number;
};

export type ChassisViewModel = {
  schemaVersion: "nms.chassisView.v1";
  generatedAt: string;
  deviceId: string;
  profileId: string;
  platform: string;
  views: ChassisViewImage[];
  tree: ChassisTreeNode[];
  componentsById: Record<string, ChassisComponent>;
  physicalIndexToComponentId: Record<string, string>;
  alarmsByComponentId?: Record<string, ComponentAlarmInfo>;
  alarmSummary?: AlarmSummary;
  source?: {
    type?: string;
    profile?: string;
    physicalInventory?: {
      available: number;
      matched: number;
      unmatched: number;
    };
  };
};
