# Biometric Device Integration (`hr_zk_attendance`)

Odoo 17 module integrating ZKTeco biometric devices (e.g. uFace 202) with `hr.attendance`, including **real-time ADMS push support for Odoo.sh** and a **shift-based attendance rules engine** (late / short leave / half leave / rest day / absent).

> This module was originally built on a base ZKTeco/biometric device integration module (not built from scratch). The **ADMS real-time push integration for Odoo.sh** and the **shift/attendance rules logic** described below were added on top of that base.

## Overview

The module lets biometric devices push attendance punches straight into Odoo and automatically classifies each punch against the employee's assigned shift (on time / late / short leave / absent / rest day / etc.), keeping payroll and attendance reporting in sync.

## Key Features

### Real-time ADMS integration (Odoo.sh-ready)
- Implements ZKTeco's **ADMS ("Cloud Server") push protocol**, so devices push attendance data directly to this Odoo instance instead of Odoo needing to poll or connect into the office LAN.
- Because the device initiates the connection, this works cleanly on **Odoo.sh** or any cloud-hosted Odoo — no inbound network access into the office is required.
- Multiple devices supported simultaneously: each device is registered as a `biometric.device.details` record with its Serial Number, and every push includes that serial (`SN` parameter) to route data to the right device record — nothing is hardcoded to a single machine.
- Endpoints implemented (`controllers/zk_adms_controller.py`):
  - `GET /iclock/cdata` — device handshake / requests push configuration (real-time mode is enabled via `Realtime=1` in the response).
  - `POST /iclock/cdata` — device pushes attendance records (parsed and processed into Odoo attendance data).
  - `GET /iclock/getrequest` — device polls for pending server commands.
  - `POST /iclock/devicecmd` — device reports back a command's execution result.
- Unregistered devices are safely ignored (with a log warning) rather than causing errors.

### Shift-based attendance rules engine
- `employee.shift` model defines shifts (Morning/Evening/Night/Gazette Morning/Gazette Night) with configurable **Shift Start**, **Margin**, **Late End**, **Short Leave**, and **Shift Duration**, with `Shift End`/`Present End`/`Late End` auto-computed from these.
- Each shift can optionally link to a `resource.calendar` (Working Schedule) — when a shift is assigned to an employee, that Working Schedule is also applied to their contract, keeping payroll/overtime calculations aligned with attendance.
- Shifts go through an **approval workflow** (Draft → HR Approval → Approved, with Cancel/Reject).
- `hr.attendance` is extended with the rules logic (`action_shift_now`) that compares each check-in/check-out against the assigned shift's thresholds to classify it as:
  - Present (on time), Late, Short Leave, Half Leave, Absent, or Rest Day
  - Also tracks **Late Check In** and **Early Check Out** durations.
- A broader `Leave Status` field consolidates attendance status with leave types (Paid/Unpaid/Casual/Sick/Compensatory/Gazette/Official Leave, Work From Home, Outdoor Duty).
- Rest days can be flagged per attendance record (`is_rest_day`), which auto-fills the record as a rest day and clears late/early figures.
- Bulk shift management via the **Bulk Shift Change** wizard, and a **Shift Adjustment** wizard for manual corrections.

## Module Structure

```
hr_zk_attendance/
├── __init__.py
├── __manifest__.py
├── controllers/
│   └── zk_adms_controller.py       # ADMS real-time push receiver (Odoo.sh-ready)
├── models/
│   ├── biometic_machine_data.py
│   ├── biometric_device_details.py # registered device records (Serial Number, etc.)
│   ├── daily_attendance.py         # SQL-view based attendance report
│   ├── employee_shift.py           # shift definitions + approval workflow
│   ├── hr_attendance.py            # shift-based rules engine (late/short leave/absent/etc.)
│   ├── hr_contract.py
│   ├── hr_employee.py
│   ├── hr_rest_day.py
│   ├── res_users.py
│   ├── resource_calendar.py
│   └── zk_machine_attendance.py    # raw punches received from devices
├── wizard/
│   ├── bulk_shift_change.py/.xml
│   └── shift_adjustment.py/.xml
├── data/
│   ├── biometric_cron.xml
│   └── rest_days.xml
├── views/                          # backend views for all the above
└── security/
    ├── groups.xml
    └── ir.model.access.csv
```

## Dependencies

- Odoo apps: `base_setup`, `hr_attendance`, `hr_contract`, `hr`, `resource`
- Python library: `pyzk` (required for ADMS attendance parsing — `pip install pyzk`)

## Installation

1. Copy the `hr_zk_attendance` folder into your Odoo `custom_addons` directory.
2. Ensure the `pyzk` Python library is installed on the server.
3. Update the Apps list (Settings → Apps → Update Apps List).
4. Search for **Biometric Device Integration** and click Install.

## Setup (ADMS real-time push)

1. Create a **Biometric Device** record in Odoo and fill in the device's **Serial Number**.
2. On the physical device, go to **Comm → Cloud Server Setting**, set **Server Mode = ADMS**, and point the server address/port at this Odoo instance's domain (works on Odoo.sh out of the box since no inbound connection is needed).
3. The device will handshake at `/iclock/cdata` and begin pushing attendance in real time; pushes are matched to the correct device record via the Serial Number and processed automatically.

## Setup (Shifts & rules)

1. Create **Employee Shifts** (Attendance/HR menu) with the appropriate Start/Margin/Late End/Short Leave values, and optionally link a Working Schedule.
2. Push the shift through its approval workflow (Draft → HR Approval → Approved).
3. Assign shifts to employees individually or via the **Bulk Shift Change** wizard.
4. As attendance records come in (from device pushes or manual entry), use **Shift Adjustment** or the automatic rules engine to classify each record's status.

## License

AGPL-3

## Author

Umair Abbas — Rainbow Printing Solutions
