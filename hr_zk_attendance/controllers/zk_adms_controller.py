# -*- coding: utf-8 -*-
"""
ADMS ("Cloud Server") push receiver for ZKTeco biometric devices.

When a device is configured with Comm > Cloud Server Setting > Server
Mode = ADMS, pointed at this Odoo instance's domain/port, the device
initiates all connections itself and pushes attendance data straight
here. No inbound connection into the office LAN is ever required, so
this works cleanly on odoo.sh (or any cloud-hosted Odoo).

Multiple devices are supported: each physical device must first be
registered as a biometric.device.details record with its Serial
Number filled in (Device form > Serial Number field). Every request
a device sends includes its own serial number (the "SN" query
parameter); we use it to look up the matching record and route data
accordingly, so nothing is hardcoded to one machine.

Endpoints implemented (the minimum ZKTeco's ADMS protocol requires):
  GET  /iclock/cdata        -> handshake / device requests its config
  POST /iclock/cdata        -> device pushes attendance records
  GET  /iclock/getrequest   -> device polls for pending server commands
  POST /iclock/devicecmd    -> device reports a command's execution result
"""

import logging
from datetime import datetime

from odoo import http
from odoo.http import request

try:
    from zk.attendance import Attendance
except ImportError:
    Attendance = None
    logging.getLogger(__name__).error("Please install the pyzk library.")

_logger = logging.getLogger(__name__)


class ZkAdmsController(http.Controller):

    def _get_device(self, serial_no):
        """Find the registered device record for this serial number.
        Uses sudo() since ADMS requests arrive with no logged-in user
        (auth='none') — the device itself has no Odoo credentials."""
        if not serial_no:
            return None
        return (
            request.env["biometric.device.details"]
            .sudo()
            .search([("serial_no", "=", serial_no)], limit=1)
        )

    @staticmethod
    def _text_response(body):
        return request.make_response(body, headers=[("Content-Type", "text/plain")])

    @http.route("/iclock/cdata", type="http", auth="none", methods=["GET", "POST"], csrf=False)
    def iclock_cdata(self, **kwargs):
        serial_no = kwargs.get("SN") or kwargs.get("sn")
        device = self._get_device(serial_no)

        if request.httprequest.method == "GET":
            # Handshake — the device is requesting its push configuration.
            if not device:
                _logger.warning(
                    "ADMS handshake from unregistered device SN=%s. "
                    "Add a Biometric Device record with this Serial Number "
                    "in Odoo to accept its data.", serial_no,
                )
                return self._text_response("ERROR: Unregistered device")

            config = (
                "GET OPTION FROM: {sn}\n"
                "Stamp=9999\n"
                "TimeZone=5\n"
                "OpStamp=9999\n"
                "ErrorDelay=60\n"
                "Delay=30\n"
                "TransFlag=1111000000\n"
                "TransInterval=1\n"
                "TransTables=ATTLOG\n"
                "Realtime=1\n"
                "Encrypt=0\n"
            ).format(sn=serial_no)
            return self._text_response(config)

        # POST — the device is pushing actual attendance records.
        if not device:
            _logger.warning(
                "ADMS data push from unregistered device SN=%s ignored.",
                serial_no,
            )
            return self._text_response("OK: 0")

        raw_body = request.httprequest.get_data(as_text=True) or ""
        attendances = []
        for line in raw_body.strip().splitlines():
            # ADMS ATTLOG line format: PIN, TIME, STATUS, VERIFY, WORKCODE, ...
            #   STATUS = check-in/out state (not used by this module's
            #            attendance_type field)
            #   VERIFY = verification method (finger/face/card/password) -
            #            this is what the module's attendance_type field
            #            (Selection: 1=Finger, 15=Face, 2=Type_2,
            #            3=Password, 4=Card, 255=Duplicate) expects.
            fields_in_line = line.strip().split("\t")
            if len(fields_in_line) < 3:
                continue
            pin, timestamp_str = fields_in_line[0], fields_in_line[1]
            verify = fields_in_line[3] if len(fields_in_line) > 3 else "1"
            try:
                punch_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            try:
                verify_val = int(verify)
            except ValueError:
                verify_val = 1
            # Only known/valid values for attendance_type; anything else
            # falls back to 1 (Finger) rather than crashing the create().
            if str(verify_val) not in ("1", "15", "2", "3", "4", "255"):
                verify_val = 1
            attendances.append(Attendance(user_id=pin, timestamp=punch_dt, status=verify_val))

        if attendances:
            try:
                device._process_attendance_batch(device, device.device_ip, attendances)
            except Exception:
                _logger.exception("Failed processing ADMS push from SN=%s", serial_no)

        _logger.info(
            "ADMS push: %s record(s) received from SN=%s (%s)",
            len(attendances), serial_no, device.name,
        )
        return self._text_response(f"OK: {len(attendances)}")

    @http.route("/iclock/getrequest", type="http", auth="none", methods=["GET"], csrf=False)
    def iclock_getrequest(self, **kwargs):
        # Device polls periodically for pending server-issued commands.
        # We don't issue any, so always tell it there's nothing to do.
        return self._text_response("OK")

    @http.route("/iclock/devicecmd", type="http", auth="none", methods=["POST"], csrf=False)
    def iclock_devicecmd(self, **kwargs):
        # Device reports back the result of a command we never sent.
        return self._text_response("OK")