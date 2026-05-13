"""EPNM 4.0 task-permission catalog and built-in roles (from User and Administrator Guide)."""

from __future__ import annotations

import re

# (category, task_name, description)
_CATALOG_ROWS: list[tuple[str, str, str]] = [
    ("Administrative Operations", "Appliance", "Allows users to access appliances"),
    ("Administrative Operations", "Application Server Management Access", "Allows users to access and manage the application server"),
    ("Administrative Operations", "Application and Services Access", "Allows users to access application and their services"),
    ("Administrative Operations", "Cisco DNA Center coexistence", "Allows the users to access Cisco DNA center"),
    ("Administrative Operations", "Data Migration", "Allows the users to Data Migration"),
    ("Administrative Operations", "Design Endpoint Site Association Access", "Allows the users to access design endpoint sites"),
    ("Administrative Operations", "Device Console Config", "Allows user to run configuration commands on Device Console"),
    ("Administrative Operations", "Device Console Show", "Allows user to run show commands on Device Console"),
    ("Administrative Operations", "Export Audit Logs Access", "Allows user to access Import Policy Update through Admin main menu"),
    ("Administrative Operations", "Health Monitor Details", "Allows user to modify Site Health Score definitions"),
    ("Administrative Operations", "High Availability Configuration", "Allows user to configure High Availability for pairing primary and secondary servers"),
    ("Administrative Operations", "Import Policy Update", "Allow user to manually download and import the policy updates into the compliance and Audit manager engine"),
    ("Administrative Operations", "License Center/Smart License", "Allows users to access license center/smart license"),
    ("Administrative Operations", "Logging", "Gives access to the log modules menu item which allows user to configure the logging levels"),
    ("Administrative Operations", "Scheduled Tasks and Data Collection", "Controls access to the screen to view the background tasks"),
    ("Administrative Operations", "System Settings", "Controls access to the Administration > System Settings menu"),
    ("Administrative Operations", "User Defined Fields", "Allows user to create user defined fields"),
    ("Administrative Operations", "User Preferences", "Controls access to the Administration > User Preference menu"),
    ("Administrative Operations", "View Audit Logs Access", "Allows user to view Network and System audits"),
    ("Administrative Operations", "Audit Trails", "Allows users to access audit trails"),
    ("Administrative Operations", "LDAP Server", "Allows users to access LDAP servers"),
    ("Administrative Operations", "RADIUS Servers", "Allows users to access RADIUS servers"),
    ("Administrative Operations", "SSO Server AAA Mode", "Allows users to access SSO servers in AAA mode only"),
    ("Administrative Operations", "SSO Servers", "Allows users to access SSO Servers"),
    ("Administrative Operations", "TACACS+ Servers", "Allows users to access TACACS+ servers"),
    ("Administrative Operations", "Users and Groups", "Allows users to access users and groups"),
    ("Administrative Operations", "Virtual Domain Management", "Allows users to manage virtual domains"),

    ("Alerts and Events", "Ack and Unack Alerts", "Allows user to acknowledge or unacknowledge existing alarms"),
    ("Alerts and Events", "Alarm Policies", "Allows user to access alarm policies"),
    ("Alerts and Events", "Alarm Policies Edit Access", "Allows user to edit alarm policies"),
    ("Alerts and Events", "Delete and Clear Alerts", "Allows user to clear and delete active alarms"),
    ("Alerts and Events", "Email Notification", "Allows user to configure email notification forwarding"),
    ("Alerts and Events", "Notification Policies Read Access", "Allows user to view alarm notification policy"),
    ("Alerts and Events", "Notification Policies Read-Write Access", "Allows user to configure alarm notification policy"),
    ("Alerts and Events", "Pick and Unpick Alerts", "Allows user to pick and unpick alerts"),
    ("Alerts and Events", "Troubleshoot", "Allows user to do basic troubleshooting, such as traceroute and ping, on alarms"),
    ("Alerts and Events", "View Alert Condition", "Allows user to view alert conditions and controls access to the Alarm Severity and Auto Clear page. This restriction applies only to non-root users."),
    ("Alerts and Events", "View Alerts and Events", "Allows user to view a list of events and alarms"),

    ("Background Ajax Call", "License Check", "Allows user to check validity of license, Controller license and MSE license"),

    ("Configure Menu", "Configure Menu Access", "Allows user to access all features under Configuration Menu"),
    ("Configure Menu", "Unsanitized Device Config Export", "Allows user to expose unsanitized Configuration Archive"),

    ("Feedback and Support", "Automated Feedback", "Allows access to automatic feedback"),
    ("Feedback and Support", "TAC Case Management Tool", "Allows user to open a TAC case"),

    ("Global Variable Configuration", "Global Variable Access", "Allows user to access global variables"),

    ("Groups Management", "Add Group Members", "Allows user to add an entity, such as a device or port, to Network Device Groups"),
    ("Groups Management", "Add Groups", "Allows user to create Network Device Groups"),
    ("Groups Management", "Delete Group Members", "Allows user to remove members from Network Device Groups"),
    ("Groups Management", "Delete Groups", "Allows user to delete Network Device Groups"),
    ("Groups Management", "Export Groups", "Allows user to export Network Device Groups"),
    ("Groups Management", "Import Groups", "Allows user to import Network Device Groups"),
    ("Groups Management", "Modify Groups", "Allows user to edit Network Device Groups attributes such as name, parent, and rules"),

    ("Help Menu", "Help Menu Access", "Allows user to access Help Menu"),
    ("Home Menu", "Home Menu Access", "Allows user to access Homepage"),

    ("Job Management", "Approve Job", "Allows user to submit a job for approval by another user"),
    ("Job Management", "Cancel Job", "Allows user to cancel the running jobs"),
    ("Job Management", "Delete Job", "Allows user to delete jobs from job dashboard"),
    ("Job Management", "Edit Job", "Allows user to edit jobs from job dashboard"),
    ("Job Management", "Pause Job", "Allows user to pause running and system jobs"),
    ("Job Management", "Schedule Job", "Allows user to schedule jobs"),
    ("Job Management", "View Job", "Allows user to view scheduled jobs"),
    ("Job Management", "Config Deploy Edit Job", "Allows users to edit created configuration deployment jobs and modify deployment job details before submission, approval, or deployment to devices"),
    ("Job Management", "Device Config Backup Job Edit Access", "Allows user to change the external backup settings such as repository and file encryption password"),
    ("Job Management", "Job Notification Mail", "Allows user to configure notification mails for various job types"),
    ("Job Management", "Run Job", "Allows user to run paused and scheduled jobs"),
    ("Job Management", "System Jobs Tab Access", "Allows user to view the system jobs"),
    ("Job Management", "Device Logs Collection Jobs Access", "Allows users to download logs remotely from a device via Cisco EPN Manager"),

    ("Monitor Menu", "Monitor Menu Access", "Allows user to access all features under Monitor Menu"),

    ("Network Configuration", "Add Device Access", "Allows user to add devices to Cisco EPN Manager"),
    ("Network Configuration", "Admin Templates Write Access", "Allows the users to have write access for admin templates"),
    ("Network Configuration", "Auto Provisioning", "Allows access to auto provisioning"),
    ("Network Configuration", "Alarm Monitor Policies", "Allows access to Alarm monitor policies"),
    ("Network Configuration", "Compliance Audit Fix Access", "Allows user to view, schedule and export compliance fix job/report"),
    ("Network Configuration", "Compliance Audit PAS Access", "Allows user to view, schedule and export PSIRT and EOX job/report"),
    ("Network Configuration", "Compliance Audit Policy Access", "Allows user to create, modify, delete, import and export compliance policy"),
    ("Network Configuration", "Compliance Audit Profile Access", "Allows user to view, schedule and export compliance audit job or report; view and download violations summary"),
    ("Network Configuration", "Compliance Audit Profile Edit Access", "Allows user to create, modify and delete compliance profiles; view, schedule and export compliance audit job/report"),
    ("Network Configuration", "Config Archive Read Task", "Allows config archive read access"),
    ("Network Configuration", "Config Archive Read-Write Task", "Allows config archive read-write access"),
    ("Network Configuration", "Configlet Access", "Allows Configlet access"),
    ("Network Configuration", "Configuration Templates Read Access", "Allows to access configuration templates in read-only mode"),
    ("Network Configuration", "Configure ACS View Servers", "Allows users to configure ACS view servers"),
    ("Network Configuration", "Configure Access Points", "Allows users to configure access points"),
    ("Network Configuration", "Configure Autonomous Access Point Templates", "Allows users to access autonomous access point templates"),
    ("Network Configuration", "Configure Choke Points", "Allows users to configure choke points"),
    ("Network Configuration", "Configure Config Groups", "Allows access to Config Group"),
    ("Network Configuration", "Configure Controllers", "Allows users to configure controllers"),
    ("Network Configuration", "Configure Ethernet Switch Ports", "Allows the user to access ethernet switch ports"),
    ("Network Configuration", "Configure Ethernet Switches", "Allows the user to access ethernet switches"),
    ("Network Configuration", "Configure ISE Servers", "Allows users to manage ISE servers on Cisco EPN Manager"),
    ("Network Configuration", "Configure Lightweight Access Point Templates", "Allows users to access lightweight access point templates"),
    ("Network Configuration", "Configure Mobility Devices", "Allows users to access mobility devices"),
    ("Network Configuration", "Configure Spectrum Experts", "Allows the users to configure spectrum experts"),
    ("Network Configuration", "Configure Switch Location Configuration Templates", "Allows users to access switch location configuration templates"),
    ("Network Configuration", "Configure Templates", "Allows the user to do the CRUD operation of Feature Templates and configuration Template"),
    ("Network Configuration", "Configure Third Party Controllers and Access Point", "Allows the user to configure third party controllers and access points"),
    ("Network Configuration", "Configure WIPS Profiles", "Allows the user to access WIPS profiles"),
    ("Network Configuration", "Configure WiFi TDOA Receivers", "Allows the users to configure WiFi TDOA receivers"),
    ("Network Configuration", "Credential Profile Add/Edit Access", "Allows user to add and edit credential profile"),
    ("Network Configuration", "Credential Profile Delete Access", "Allows user to delete credential profile"),
    ("Network Configuration", "Credential Profile View Access", "Allows user to view credential profile"),
    ("Network Configuration", "Delete Device Access", "Allows user to delete devices from Cisco EPN Manager"),
    ("Network Configuration", "Deploy Configuring Access", "Allows user to deploy Configuration and IWAN templates"),
    ("Network Configuration", "Design Configuration Template Access", "Allows user to create Configuration > Shared Policy Object templates and Configuration Group templates"),
    ("Network Configuration", "Device Bulk Import Access", "Allows user to perform bulk import of devices from CSV files"),
    ("Network Configuration", "Device View Configuration Access", "Allows user to configure devices in the Device Work Center"),
    ("Network Configuration", "Edit Device Access", "Allows user to edit device credentials and other device details"),
    ("Network Configuration", "Export Device Access", "Allows user to export the list of devices, including credentials, as a CSV file"),
    ("Network Configuration", "Global SSID Groups", "Allows user to access the Global SSID groups"),
    ("Network Configuration", "MBC UI Framework Access", "Allows the user to access MBC UI framework"),
    ("Network Configuration", "Migration Templates", "Allows the user to access migration templates"),
    ("Network Configuration", "Device WorkCenter", "Allows the user to access device WorkCenter"),
    ("Network Configuration", "Network Topology Edit", "Allows user to create devices, links and network in the topology map, edit the manually created link to assign the interface"),
    ("Network Configuration", "Provisioning Access", "Allows access to Provisioning"),
    ("Network Configuration", "QoS Profile Configuration Access", "Allows user to create, modify, delete QoS profiles and schedule QoS profiles deployment job or associate/disassociate interface and Import/Export QoS discovered profiles"),
    ("Network Configuration", "Scheduled Configuration Tasks", "Allows the user to edit scheduled configuration tasks"),
    ("Network Configuration", "TrustSec Readiness Assessment", "Allows the user to access the TrustSec readiness assessment details"),
    ("Network Configuration", "View Compute Devices", "Allows the user to view compute devices"),
    ("Network Configuration", "WIPS Service", "Allows the user to access WIPS services"),

    ("Network Monitoring", "Ack and Unack Security Index Issues", "Allows user to access the Ack and Unack Security Index Issues"),
    ("Network Monitoring", "Admin Dashboard Access", "Allows user to access the Admin Dashboard"),
    ("Network Monitoring", "Chassis View Read", "Allows chassis view read access"),
    ("Network Monitoring", "Chassis View Read-Write", "Allows chassis view read-write access"),
    ("Network Monitoring", "Config Audit Dashboard", "Allows users to access Config Audit Dashboard"),
    ("Network Monitoring", "Data Collection Management Access", "Allow user to access the Assurance Data Sources page"),
    ("Network Monitoring", "Details Dashboard Access", "Allow user to access the Detail dashboards"),
    ("Network Monitoring", "Disable Clients", "Allows the user to disable clients"),
    ("Network Monitoring", "Identify Unknown Users", "Allows the user to identify any unknown user"),
    ("Network Monitoring", "Incidents Alarms Events Access", "Allows user to access incidents alarms events"),
    ("Network Monitoring", "Latest Config Audit Report", "Allows user to view the latest config audit reports"),
    ("Network Monitoring", "Lync Monitoring Access", "Gives the user lync monitoring access"),
    ("Network Monitoring", "Monitor Access Points", "Allows the user to monitor the access points on the network"),
    ("Network Monitoring", "Monitor Clients", "Allows the user to monitor clients on the network"),
    ("Network Monitoring", "Monitor Controllers", "Allows the user to monitor controllers"),
    ("Network Monitoring", "Monitor Ethernet Switches", "Allows the user to monitor ethernet switches in the network"),
    ("Network Monitoring", "Monitor Interferers", "Allows the user to monitor interferers"),
    ("Network Monitoring", "Monitor Media Streams", "Allows the user to monitor media streams"),
    ("Network Monitoring", "Monitor Mobility Devices", "Allows the user to monitor mobility devices on the network"),
    ("Network Monitoring", "Monitor Security", "Gives the user access to monitor security"),
    ("Network Monitoring", "Monitor Spectrum Experts", "Allows the user to monitor spectrum experts"),
    ("Network Monitoring", "Monitor Tags", "Allows the user to monitor Tags"),
    ("Network Monitoring", "Monitor Third Party Controllers and Access Point", "Allows the user to monitor third party controllers and access points in the network"),
    ("Network Monitoring", "Monitor WiFi TDOA Receivers", "Allows the user to monitor WiFi TDOA receivers"),
    ("Network Monitoring", "Monitoring Interfaces", "Gives the user access to Monitoring Interfaces"),
    ("Network Monitoring", "Monitoring Policies", "Gives the user access to Monitoring Policies"),
    ("Network Monitoring", "Network Topology", "Allows users to launch the Network Topology map and view the devices and links in the map"),
    ("Network Monitoring", "Packet Capture Access", "Gives the user Packet Capture access"),
    ("Network Monitoring", "Performance Dashboard Access", "Allows the user to access the Performance dashboard"),
    ("Network Monitoring", "PfR Monitoring Access", "Gives the user access to PfR Monitoring"),
    ("Network Monitoring", "RRM Dashboard", "Allows the user to access the RRM dashboard"),
    ("Network Monitoring", "Remove Clients", "Gives the user permission to remove clients on the network"),
    ("Network Monitoring", "Service Health Access", "Allows the user to monitor service health"),
    ("Network Monitoring", "Site Visibility Access", "Gives the user access to Site Visibility"),
    ("Network Monitoring", "Track Clients", "Gives the user the ability to track clients"),
    ("Network Monitoring", "View Security Index Issues", "Allows the user to view any security index issues"),
    ("Network Monitoring", "Voice Diagnostics", "Allows the user to access voice diagnostics"),
    ("Network Monitoring", "Wireless Dashboard Access", "Allows the user to access wireless dashboard"),

    ("OTDR", "OTDR Configure Profiles", "Allows access to OTDR configure profiles"),
    ("OTDR", "OTDR Run Scans", "Allows user access to OTDR scans"),
    ("OTDR", "OTDR Set Baselines", "Allows access to OTDR baselines"),
    ("OTDR", "OTDR View Scan Results", "Allows user to view OTDR scan results"),

    ("Product Usage", "Product Feedback", "Allows user to access Help Us Improve page"),

    ("Reports", "CE Performance Reports", "Allows user to create the CE performance report"),
    ("Reports", "CE Performance Reports Read Only", "Allows user to create the read only CE performance report"),
    ("Reports", "Device Reports", "Allow user to run reports specific to monitoring specific report related to Devices"),
    ("Reports", "Device Reports Read Only", "Allows user to read generated device reports"),
    ("Reports", "Network Summary Reports", "Allows user to create and run network summary reports"),
    ("Reports", "Network Summary Reports Read Only", "Allows user to view all Summary reports"),
    ("Reports", "Optical Performance Reports", "Allows user to create Optical performance reports"),
    ("Reports", "Optical Performance Reports Read Only", "Allows user to view Optical performance reports"),
    ("Reports", "Performance Reports", "Allows user to create performance reports"),
    ("Reports", "Performance Reports Read Only", "Allows user to view performance reports"),
    ("Reports", "Report Launch Pad", "Allows user to access the Report page"),
    ("Reports", "Saved Reports List", "Allows user to save reports"),
    ("Reports", "System Monitoring Reports", "Allows user to view System Monitoring Reports"),
    ("Reports", "System Monitoring Reports Read Only", "Allows user to view the read only system monitoring reports"),
    ("Reports", "Virtual Domains List", "Allows user to create the Virtual Domain related report"),

    ("Software Image Management", "Add Software Image Management Servers", "Allows user to add software image management servers"),
    ("Software Image Management", "Image Details View", "Allows user to view the image details"),
    ("Software Image Management", "Manage Protocol", "Allows user to manage the Protocols"),
    ("Software Image Management", "Swim Access Privilege", "Swim access privilege"),
    ("Software Image Management", "Swim Activation", "Swim activation"),
    ("Software Image Management", "Swim Collection", "Swim collection"),
    ("Software Image Management", "Swim Delete", "Swim delete"),
    ("Software Image Management", "Swim Distribution", "Swim distribution"),
    ("Software Image Management", "Swim Preference Save", "Allows user to save preference options on System Settings > Image Management page"),
    ("Software Image Management", "Software Info Update", "Allows the user to edit and save image properties such as minimum RAM, minimum FLASH and minimum boot ROM version"),
    ("Software Image Management", "Swim Recommendation", "Allows user to recommend images from Cisco.com and from the local repository"),
    ("Software Image Management", "Swim Upgrade Analysis", "Allows user to analyze software images to determine if hardware upgrades (boot ROM, flash memory, RAM, and boot flash) are required before performing a software upgrade"),

    ("User Administration", "Audit Trails", "Allows user to access the Audit trails on user login and logout"),
    ("User Administration", "LDAP Server", "Allows user to access the LDAP Server menu"),
    ("User Administration", "RADIUS Servers", "Allows user to access the RADIUS Servers menu"),
    ("User Administration", "SSO Server AAA Mode", "Allows user to access the AAA menu"),
    ("User Administration", "SSO Servers", "Allows user to access the SSO menu"),
    ("User Administration", "TACACS+ Servers", "Allows user to access the TACACS+ Servers menu"),
    ("User Administration", "Users and Groups", "Allows user to access the Users and Groups menu"),
    ("User Administration", "Virtual Domain Management", "Allows user to access the Virtual Domain Management menu"),
    ("User Administration", "Virtual Elements Tab Access", "When creating a virtual domain or adding members to a virtual domain, it allows the user to access the virtual elements tab, enabling the user to add virtual elements (Datacenters, Clusters, and Hosts) to the virtual domain"),
]


def _slug(category: str, task: str) -> str:
    base = f"{category} {task}".lower()
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return base


def build_catalog() -> tuple[
    dict[str, list[dict[str, str]]],
    dict[str, str],
]:
    """Return (grouped catalog, key->description map)."""
    grouped: dict[str, list[dict[str, str]]] = {}
    descriptions: dict[str, str] = {}
    seen_keys: set[str] = set()
    for category, task, desc in _CATALOG_ROWS:
        key = _slug(category, task)
        # Disambiguate duplicate task names within different categories.
        i = 2
        while key in seen_keys:
            key = f"{_slug(category, task)}_{i}"
            i += 1
        seen_keys.add(key)
        grouped.setdefault(category, []).append({"key": key, "label": task, "description": desc})
        descriptions[key] = desc
    return grouped, descriptions


PERMISSION_CATALOG, PERMISSION_DESCRIPTIONS = build_catalog()


# Additional Permissions for System Settings Submenus (Table 2, EPNM 4.0).
SYSTEM_SETTINGS_SUBMENUS: list[dict[str, str]] = [
    {"task_group": "General", "task_name": "Account Settings", "additional_permission": "System Settings"},
    {"task_group": "General", "task_name": "Data Retention", "additional_permission": "System Settings"},
    {"task_group": "General", "task_name": "Job Approval", "additional_permission": "System Settings"},
    {"task_group": "General", "task_name": "Login Disclaimer", "additional_permission": "System Settings"},
    {"task_group": "General", "task_name": "Report", "additional_permission": "System Settings"},
    {"task_group": "General", "task_name": "Server", "additional_permission": "System Settings"},
    {"task_group": "General", "task_name": "Software Update", "additional_permission": "System Settings"},
    {"task_group": "General", "task_name": "User Defined Fields", "additional_permission": "System Settings"},
    {"task_group": "Mail & Notification", "task_name": "Change Audit Notification", "additional_permission": "System Settings"},
    {"task_group": "Mail & Notification", "task_name": "Mail Server Configuration", "additional_permission": "System Settings"},
    {"task_group": "Mail & Notification", "task_name": "Notification Destination", "additional_permission": "Notification Policies Read Access or Notification Policies Read-Write Access"},
    {"task_group": "Network and Device", "task_name": "SNMP", "additional_permission": "System Settings"},
    {"task_group": "Inventory", "task_name": "Configuration", "additional_permission": "System Settings"},
    {"task_group": "Inventory", "task_name": "Configuration Archive", "additional_permission": "System Settings"},
    {"task_group": "Inventory", "task_name": "Network Discovery", "additional_permission": "System Settings"},
    {"task_group": "Inventory", "task_name": "Software Image Management", "additional_permission": "System Settings"},
    {"task_group": "Inventory", "task_name": "Inventory", "additional_permission": "System Settings"},
    {"task_group": "Inventory", "task_name": "SRRG Pool Types", "additional_permission": "Network Topology"},
    {"task_group": "Inventory", "task_name": "SRRG Pool", "additional_permission": "Network Topology"},
    {"task_group": "Inventory", "task_name": "Sync Offline Devices", "additional_permission": "System Settings"},
    {"task_group": "Maps", "task_name": "Network Topology", "additional_permission": "Network Topology"},
    {"task_group": "Maps", "task_name": "Bandwidth Utilization", "additional_permission": "Network Topology"},
    {"task_group": "Circuit VCs", "task_name": "Discovery settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting"},
    {"task_group": "Circuit VCs", "task_name": "Circuits VCs Display", "additional_permission": "Circuit or VC Monitoring and Troubleshooting"},
    {"task_group": "Circuit VCs", "task_name": "Archive Settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting"},
    {"task_group": "Circuit VCs", "task_name": "Deployment Settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting"},
    {"task_group": "Circuit VCs", "task_name": "WAE Server Settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting"},
    {"task_group": "Alarm and Events", "task_name": "Alarm and Events", "additional_permission": "System Settings"},
    {"task_group": "Alarm and Events", "task_name": "Alarm Severity and Auto Clear", "additional_permission": "System Settings"},
    {"task_group": "Alarm and Events", "task_name": "System Event Configuration", "additional_permission": "System Settings"},
    {"task_group": "Alarm and Events", "task_name": "Alarm Notification Policies", "additional_permission": "Notification Policies Read Access or Notification Policies Read-Write Access"},
    {"task_group": "Performance", "task_name": "PTP/SyncE", "additional_permission": "Performance Dashboard"},
]

# Slugify each submenu so it can be a permission key as well.
for _row in SYSTEM_SETTINGS_SUBMENUS:
    _row["permission_key"] = _slug(f"System Settings Submenu {_row['task_group']}", _row["task_name"])
    PERMISSION_DESCRIPTIONS[_row["permission_key"]] = f"{_row['task_name']} ({_row['task_group']}). Additional permission required: {_row['additional_permission']}."

# Add a synthetic catalog category for the submenu permissions so they show up
# alongside other task permissions.
PERMISSION_CATALOG["Additional Permissions for System Settings Submenus"] = [
    {"key": row["permission_key"], "label": f"{row['task_group']} — {row['task_name']}", "description": PERMISSION_DESCRIPTIONS[row["permission_key"]]}
    for row in SYSTEM_SETTINGS_SUBMENUS
]


def all_permission_keys() -> set[str]:
    keys: set[str] = {"*", "root.manage", "nbi.read", "nbi.write"}
    for items in PERMISSION_CATALOG.values():
        keys.update(item["key"] for item in items)
    return keys


# Built-in EPNM roles (Web UI + NBI). Names match the PDF (slug form).
def _grant(*categories: str) -> dict[str, bool]:
    grants: dict[str, bool] = {}
    for cat in categories:
        for item in PERMISSION_CATALOG.get(cat, []):
            grants[item["key"]] = True
    return grants


_ALL_WEB_CATEGORIES = [c for c in PERMISSION_CATALOG if c != "Additional Permissions for System Settings Submenus"]

BUILT_IN_ROLES: dict[str, dict] = {
    "root": {
        "display_name": "Root",
        "description": "All operations. Role permissions are not editable. Best practice: create Admin/Super Users and disable root web UI login.",
        "user_type": "web",
        "permissions": {"*": True, "root.manage": True},
        "editable": False,
    },
    "super_users": {
        "display_name": "Super Users",
        "description": "All operations (not by default). Permissions editable. Can enable permissions similar to root.",
        "user_type": "web",
        "permissions": _grant(*_ALL_WEB_CATEGORIES),
        "editable": True,
    },
    "admin": {
        "display_name": "Admin",
        "description": "Administer the system and server. Can also perform monitoring and configuration operations.",
        "user_type": "web",
        "permissions": _grant("Administrative Operations", "User Administration", "Network Configuration", "Network Monitoring", "Job Management", "Reports", "Software Image Management", "Alerts and Events", "Groups Management", "Additional Permissions for System Settings Submenus"),
        "editable": True,
    },
    "config_managers": {
        "display_name": "Config Managers",
        "description": "Configure and monitor the network (no administration tasks).",
        "user_type": "web",
        "permissions": _grant("Network Configuration", "Network Monitoring", "Job Management", "Groups Management", "Software Image Management", "Alerts and Events", "Reports"),
        "editable": True,
    },
    "system_monitoring": {
        "display_name": "System Monitoring",
        "description": "Monitor the network (no configuration tasks).",
        "user_type": "web",
        "permissions": _grant("Network Monitoring", "Alerts and Events", "Reports"),
        "editable": True,
    },
    "help_desk_admin": {
        "display_name": "Help Desk Admin",
        "description": "Access to the help desk and user-preferences pages only. Lacks access to the main UI.",
        "user_type": "web",
        "permissions": _grant("Help Menu", "Home Menu"),
        "editable": True,
    },
    "lobby_ambassador": {
        "display_name": "Lobby Ambassador",
        "description": "User administration for Guest users only. Cannot be a member of any other role.",
        "user_type": "web",
        "permissions": _grant("User Administration"),
        "editable": True,
    },
    "monitor_lite": {
        "display_name": "Monitor Lite",
        "description": "View network topology and use tags. Cannot be a member of any other role. Permissions not editable.",
        "user_type": "web",
        "permissions": {"network_monitoring_network_topology": True, "network_monitoring_monitor_tags": True},
        "editable": False,
    },
    "north_bound_api": {
        "display_name": "North Bound API",
        "description": "Access to the SOAP APIs.",
        "user_type": "nbi",
        "permissions": {"nbi.read": True},
        "editable": True,
    },
    "user_assistant": {
        "display_name": "User Assistant",
        "description": "Local Net user administration only. Cannot be a member of any other role.",
        "user_type": "web",
        "permissions": _grant("User Administration"),
        "editable": True,
    },
    "mdns_policy_admin": {
        "display_name": "mDNS Policy Admin",
        "description": "mDNS policy administration functions.",
        "user_type": "web",
        "permissions": {},
        "editable": True,
    },
    "nbi_read": {
        "display_name": "NBI Read",
        "description": "RESTCONF NBI read operations (HTTP GET). Can also belong to other NBI and web UI roles.",
        "user_type": "nbi",
        "permissions": {"nbi.read": True},
        "editable": False,
    },
    "nbi_write": {
        "display_name": "NBI Write",
        "description": "RESTCONF NBI write operations (HTTP PUT, POST, DELETE). Can also belong to other NBI and web UI roles.",
        "user_type": "nbi",
        "permissions": {"nbi.read": True, "nbi.write": True},
        "editable": False,
    },
}

# User-Defined 1..5: blank, renamable, customizable.
for _i in range(1, 6):
    BUILT_IN_ROLES[f"user_defined_{_i}"] = {
        "display_name": f"User-Defined {_i}",
        "description": "Blank role; rename and customize as required.",
        "user_type": "web",
        "permissions": {},
        "editable": True,
    }


__all__ = [
    "PERMISSION_CATALOG",
    "PERMISSION_DESCRIPTIONS",
    "SYSTEM_SETTINGS_SUBMENUS",
    "BUILT_IN_ROLES",
    "all_permission_keys",
]
