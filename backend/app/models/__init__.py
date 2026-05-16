"""Models package — register all ORM models so Base.metadata sees them."""

from app.models.alarm import Alarm
from app.models.alarm_rule import AlarmRule
from app.models.command import Command
from app.models.credential import Credential
from app.models.device import Device
from app.models.inventory import Inventory
from app.models.ios_version import IOSVersion
from app.models.kpi import KPI
from app.models.mib import MIB
from app.models.topology import TopologyLink, TopologyNode
from app.models.system import AppRole, AppUser, SystemSetting

__all__ = [
    "Alarm",
    "AlarmRule",
    "Command",
    "Credential",
    "Device",
    "Inventory",
    "IOSVersion",
    "KPI",
    "MIB",
    "TopologyLink",
    "TopologyNode",
    "AppUser",
    "AppRole",
    "SystemSetting",
]
