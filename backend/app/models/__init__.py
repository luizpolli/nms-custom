"""Models package — register all ORM models so Base.metadata sees them."""

from app.models.alarm import Alarm
from app.models.alarm_filter import SavedAlarmFilter
from app.models.alarm_rule import AlarmRule
from app.models.audit import AuditLog
from app.models.command import Command
from app.models.credential import Credential, CredentialAssignment
from app.models.device import Device
from app.models.forwarding import ForwardingTarget
from app.models.inventory import Inventory
from app.models.interface import Interface
from app.models.ios_version import IOSVersion
from app.models.kpi import KPI
from app.models.kpi_threshold import KPIThreshold
from app.models.mib import MIB
from app.models.monitoring_policy import MonitoringPolicy
from app.models.physical_inventory import PhysicalInventoryComponent
from app.models.report_schedule import GeneratedReport, ReportSchedule
from app.models.service import Service, ServiceDependency, ServiceMember, ServiceScoreSnapshot
from app.models.topology import TopologyLink, TopologyNode
from app.models.system import AppRole, AppUser, SystemSetting
from app.models.telemetry import (
    TelemetryCollector,
    TelemetryIngestionStat,
    TelemetryRawSample,
    TelemetrySensorPath,
    TelemetrySubscription,
)

__all__ = [
    "Alarm",
    "SavedAlarmFilter",
    "AlarmRule",
    "AuditLog",
    "Command",
    "Credential",
    "CredentialAssignment",
    "Device",
    "ForwardingTarget",
    "Inventory",
    "Interface",
    "IOSVersion",
    "KPI",
    "KPIThreshold",
    "MIB",
    "MonitoringPolicy",
    "PhysicalInventoryComponent",
    "GeneratedReport",
    "ReportSchedule",
    "Service",
    "ServiceDependency",
    "ServiceMember",
    "ServiceScoreSnapshot",
    "TopologyLink",
    "TopologyNode",
    "AppUser",
    "AppRole",
    "SystemSetting",
    "TelemetryCollector",
    "TelemetryIngestionStat",
    "TelemetryRawSample",
    "TelemetrySensorPath",
    "TelemetrySubscription",
]
