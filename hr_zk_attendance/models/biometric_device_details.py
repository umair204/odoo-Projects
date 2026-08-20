# -*- coding: utf-8 -*-

from datetime import timedelta
from datetime import datetime, date
import logging
import pytz
from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
    from zk.attendance import Attendance
except ImportError:
    _logger.error("Please Install pyzk library.")

class BiometricDeviceDetails(models.Model):
    """Model for configuring and connect the biometric device with odoo"""

    _name = "biometric.device.details"
    _description = "Biometric Device Details"

    name = fields.Char(string="Name", required=True, help="Record Name")
    device_ip = fields.Char(string="Device IP", required=True, help="The IP address of the Device")
    port_number = fields.Integer(string="Port Number", required=True, help="The Port Number of the Device")
    address_id = fields.Many2one("res.partner", string="Working Address", help="Working address of the partner")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.user.company_id.id,
        help="Current Company",
    )
    serial_no = fields.Char(string="Device Serial Number", help="Serial Number of the Device")
    clock_offset_hours = fields.Float(
        string="Clock Offset (hours)",
        default=0.0,
        help=(
            "Use this if the device's own clock cannot be set to the correct "
            "local time/timezone (e.g. it always syncs to a fixed remote "
            "region such as China Standard Time regardless of where the "
            "device physically is). Enter how many hours AHEAD of true "
            "local time the device's clock runs; this many hours will be "
            "subtracted from every punch timestamp before it is processed. "
            "Enter a negative number if the device's clock instead runs "
            "BEHIND true local time. Leave as 0 if the device's clock is "
            "already correct."
        ),
    )

    _sql_constraints = [
        (
            "serial_no_unique",
            "unique(serial_no)",
            "A device with this Serial Number is already registered. Each device must have a unique serial number.",
        )
    ]

    def action_test_connection(self):
        """Checking the connection status"""
        zk = ZK(
            self.device_ip,
            port=self.port_number,
            timeout=30,
            password=False,
            ommit_ping=False,
        )
        try:
            if zk.connect():
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "message": "Successfully Connected",
                        "type": "success",
                        "sticky": False,
                    },
                }
        except Exception as error:
            raise ValidationError(f"{error}")

    def cron_action_download_attendance(self):
        res = self.env["biometric.device.details"].search([])
        for rec in res:
            rec.action_download_attendance()

    def device_connect(self, zk):
        """Function for connecting the device with Odoo"""
        try:
            conn = zk.connect()
            return conn
        except Exception:
            return False

    def disconnect_device(self, zk):
        """Function to disconnect the device"""
        try:
            zk.disconnect()
        except Exception:
            return False

    def _process_attendance_batch(self, info, machine_ip, attendances):
        """Process a batch of raw attendance punches (pyzk-style records
        with .timestamp, .user_id and .status attributes) into
        zk.machine.attendance / hr.attendance records, applying the same
        shift-based check-in/check-out logic used when Odoo pulls
        directly from the device. Shared by action_download_attendance
        (local device pull) and action_receive_punches (remote agent push).
        """
        zk_attendance = self.env["zk.machine.attendance"]

        offset_hours = info.clock_offset_hours or 0.0
        if offset_hours:
            for each in attendances:
                each.timestamp = each.timestamp - timedelta(hours=offset_hours)

        today = datetime.today().date()
        date_start = date(2024, 6, 1)
        print(date_start)
        todays_attendance = [each for each in attendances if each.timestamp.date() >= date_start]
        # print("=================", todays_attendance)
        if todays_attendance:
            # for each in todays_attendance:
            # atten_time = fields.Datetime.to_string(atten_time)
            # temp_atten_time = fields.Datetime.from_string(atten_time)
            start_date_check_attendance = date_start
            # print(start_date_check_attendance, "start check")
            for each in todays_attendance:
                atten_time = each.timestamp
                # NOTE: previously used self.env.user.partner_id.tz here, but
                # that depends on which Odoo user's context the code runs
                # under. When triggered by an interactive button click it's
                # whoever is logged in (usually correctly set); but ADMS
                # pushes run under sudo() as the internal system user, whose
                # partner record has no timezone set, silently falling back
                # to GMT (a no-op conversion) and causing a +5h display bug.
                # Hardcoded to match the same timezone already hardcoded
                # elsewhere in this file (see astimezone(pytz.timezone(
                # "Asia/Karachi")) calls below) so behavior is consistent
                # regardless of what triggered the processing.
                local_tz = pytz.timezone("Asia/Karachi")
                local_dt = local_tz.localize(atten_time, is_dst=None)
                utc_dt = local_dt.astimezone(pytz.utc)
                utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
                atten_time = datetime.strptime(utc_dt, "%Y-%m-%d %H:%M:%S")
                # print(each)

                timedate = datetime.strptime(
                    each.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "%Y-%m-%d %H:%M:%S",
                )
                if str(start_date_check_attendance) < str(timedate).split()[0] <= str(date.today()):
                    employee = info.env["hr.employee"].search([("device_id_num", "=", each.user_id)])
                    if employee:
                        # print("Employee: ", employee.name)
                        timendate = str(atten_time).split()
                        employee_id = self.env["hr.employee"].search([("barcode", "=", each.user_id)])
                        duplicate_atten_ids = zk_attendance.search(
                            [
                                ("employee_id", "=", employee_id.id),
                                ("punching_time", "=", atten_time),
                            ]
                        )
                        # print(duplicate_atten_ids, "duplicate_atten_ids")
                        if len(duplicate_atten_ids) > 0:
                            continue
                        else:
                            if len(employee_id) == 1:
                                shift_check = employee_id.employee_shift_id
                                if shift_check:
                                    temp_time = datetime.strptime(
                                        str(atten_time),
                                        "%Y-%m-%d %H:%M:%S",
                                    ).astimezone(pytz.timezone("Asia/Karachi"))
                                    temp_time = datetime.strptime(
                                        str(temp_time),
                                        "%Y-%m-%d %H:%M:%S+05:00",
                                    )
                                    date_check = temp_time.date()
                                    attendance_date_check = temp_time.date()
                                    if shift_check.shift_type == "Night":
                                        temp_time = datetime.strptime(
                                            str(temp_time),
                                            "%Y-%m-%d %H:%M:%S",
                                        )
                                        shift_start_today = datetime(
                                            temp_time.year,
                                            temp_time.month,
                                            temp_time.day,
                                        ) + timedelta(
                                            hours=shift_check.shift_start,
                                            seconds=-1,
                                        )
                                        margin_shift_start = shift_start_today - timedelta(hours=3)
                                        # A night shift spans midnight, so a
                                        # punch belongs to one of two
                                        # "portions" of the same shift
                                        # occurrence:
                                        #   - EVENING portion (from the
                                        #     early-arrival margin onward,
                                        #     through the shift starting and
                                        #     continuing until midnight):
                                        #     belongs to THIS calendar day's
                                        #     shift.
                                        #   - MORNING portion (after
                                        #     midnight, before the
                                        #     evening-arrival margin):
                                        #     belongs to the PREVIOUS
                                        #     calendar day's shift (the one
                                        #     that started the evening
                                        #     before).
                                        # date_check (used to anchor the
                                        # shift's start/close time windows)
                                        # and attendance_date_check (used to
                                        # find/group the matching attendance
                                        # record) must always agree on which
                                        # day that is — previously they
                                        # could disagree, which silently
                                        # broke every downstream time-window
                                        # comparison for both check-in and
                                        # check-out punches.
                                        if temp_time.time() >= margin_shift_start.time():
                                            date_check = temp_time.date()
                                            attendance_date_check = temp_time.date()
                                        else:
                                            date_check = temp_time.date() + timedelta(days=-1)
                                            attendance_date_check = temp_time.date() + timedelta(days=-1)
                                    elif shift_check.shift_type == "Evening":
                                        temp_time = datetime.strptime(
                                            str(temp_time),
                                            "%Y-%m-%d %H:%M:%S",
                                        )
                                        shift_start = datetime(
                                            temp_time.year,
                                            temp_time.month,
                                            temp_time.day,
                                        ) + timedelta(hours=shift_check.shift_start)
                                        shift_end = shift_start + timedelta(
                                            hours=(shift_check.shift_duration + 6)
                                        )
                                        start_new = shift_end.replace(hour=0, minute=0, second=0)
                                        if start_new.time() <= temp_time.time() <= shift_end.time():
                                            date_check = temp_time.date() + timedelta(days=-1)
                                            attendance_date_check = temp_time.date() + timedelta(days=-1)
                                    elif shift_check.shift_type == "Gazette Night":
                                        temp_time = datetime.strptime(
                                            str(temp_time),
                                            "%Y-%m-%d %H:%M:%S",
                                        )
                                        shift_start = datetime(
                                            temp_time.year,
                                            temp_time.month,
                                            temp_time.day,
                                        ) + timedelta(hours=shift_check.shift_start)
                                        shift_end = shift_start + timedelta(
                                            hours=(shift_check.shift_duration + 6)
                                        )
                                        start_new = shift_end.replace(hour=0, minute=0, second=0)
                                        if start_new.time() <= temp_time.time() <= shift_end.time():
                                            date_check = temp_time.date() + timedelta(days=-1)
                                            attendance_date_check = temp_time.date() + timedelta(days=-1)
                                    temp_time = datetime.strptime(
                                        str(temp_time),
                                        "%Y-%m-%d %H:%M:%S",
                                    )
                                    shift_start = datetime(
                                        date_check.year,
                                        date_check.month,
                                        date_check.day,
                                    ) + timedelta(hours=shift_check.shift_start)
                                    margin_shift_start = shift_start - timedelta(hours=3)

                                    present_end = datetime(
                                        date_check.year,
                                        date_check.month,
                                        date_check.day,
                                    ) + timedelta(hours=shift_check.present_end)
                                    late_end = datetime(
                                        date_check.year,
                                        date_check.month,
                                        date_check.day,
                                    ) + timedelta(hours=shift_check.late_end)
                                    short_end = datetime(
                                        date_check.year,
                                        date_check.month,
                                        date_check.day,
                                    ) + timedelta(hours=shift_check.short_leave)
                                    shift_end = shift_start + timedelta(
                                        hours=(shift_check.shift_duration + 6)
                                    )
                                    shift_close = shift_start + timedelta(hours=shift_check.shift_duration)
                                    shift_late_departure_margin = shift_close - timedelta(
                                        hours=shift_check.margin
                                    )
                                    shift_late_departure = shift_close - timedelta(hours=1)
                                    shift_short_departure = shift_close - timedelta(hours=2)
                                    check_record = self.env["hr.attendance"].search(
                                        [
                                            (
                                                "employee_id",
                                                "=",
                                                employee_id.id,
                                            ),
                                            (
                                                "current_shift_att_date",
                                                "=",
                                                attendance_date_check,
                                            ),
                                        ]
                                    )
                                    # print("Employee: ", employee_id.name)
                                    # print("Shift: ", shift_check.name)
                                    # print("Machine Time: ", timedate)
                                    # print("Punching Time: ", temp_time)
                                    # print(
                                    #     "Margin Start: ",
                                    #     margin_shift_start,
                                    # )
                                    # print("Shift Start: ", shift_start)
                                    # print("Present End: ", present_end)
                                    # print("Short End: ", short_end)
                                    # print("Shift End: ", shift_end)
                                    if check_record.is_absent:
                                        # print(check_record)
                                        check_record.with_context(force_delete=True).unlink()
                                        check_record = self.env["hr.attendance"]
                                        # print(check_record)
                                    if len(check_record) == 0:
                                        rest_day = employee_id.rest_days_ids.mapped("name")
                                        date_check1 = temp_time.date()
                                        if date_check1.strftime("%A") in rest_day:
                                            att_vals = {
                                                "employee_id": employee_id.id,
                                                "current_shift_att_date": attendance_date_check,
                                                "check_in": atten_time,
                                                "check_out": atten_time,
                                                "check_in_status": "presentontime",
                                                "check_out_status": "presentontime",
                                                "employee_shift_id": shift_check.id,
                                            }
                                            self.env["hr.attendance"].create(att_vals)
                                            # print(
                                            #     "Status: Rest Day Present"
                                            # )
                                        elif margin_shift_start <= temp_time < present_end:
                                            att_vals = {
                                                "employee_id": employee_id.id,
                                                "current_shift_att_date": attendance_date_check,
                                                "check_in": atten_time,
                                                "check_out": atten_time,
                                                "check_in_status": "presentontime",
                                                "check_out_status": "absent",
                                                "employee_shift_id": shift_check.id,
                                            }
                                            self.env["hr.attendance"].create(att_vals)
                                            # print("Status: Present")
                                        elif present_end <= temp_time < late_end:
                                            att_vals = {
                                                "employee_id": employee_id.id,
                                                "current_shift_att_date": attendance_date_check,
                                                "check_in": atten_time,
                                                "check_out": atten_time,
                                                "check_in_status": "late",
                                                "employee_shift_id": shift_check.id,
                                                "late_time": str(temp_time - shift_start),
                                                "check_out_status": "absent",
                                                "early_time": False,
                                            }
                                            self.env["hr.attendance"].create(att_vals)
                                            # print("Status: Late")
                                        elif late_end <= temp_time < short_end:
                                            att_vals = {
                                                "employee_id": employee_id.id,
                                                "current_shift_att_date": attendance_date_check,
                                                "check_in": atten_time,
                                                "check_out": atten_time,
                                                "employee_shift_id": shift_check.id,
                                                "check_in_status": "shortleave",
                                                "check_out_status": "absent",
                                                "late_time": str(temp_time - shift_start),
                                                "early_time": False,
                                            }
                                            self.env["hr.attendance"].create(att_vals)
                                            # print("Status: Short Leave")
                                        else:
                                            att_vals = {
                                                "employee_id": employee_id.id,
                                                "current_shift_att_date": attendance_date_check,
                                                "check_in": atten_time,
                                                "employee_shift_id": shift_check.id,
                                                "check_out": atten_time,
                                                "check_in_status": "absent",
                                                "check_out_status": "absent",
                                                "late_time": False,
                                                "early_time": False,
                                            }
                                            if shift_late_departure_margin <= temp_time:
                                                att_vals["early_time"] = False
                                                att_vals["check_out_status"] = "presentontime"
                                            elif (
                                                shift_late_departure_margin
                                                > temp_time
                                                >= shift_late_departure
                                            ):
                                                att_vals["early_time"] = str(shift_close - temp_time)
                                                att_vals["check_out_status"] = "late"
                                            elif shift_late_departure > temp_time >= shift_short_departure:
                                                att_vals["early_time"] = str(shift_close - temp_time)
                                                att_vals["check_out_status"] = "shortleave"
                                            self.env["hr.attendance"].create(att_vals)
                                    elif len(check_record) == 1:
                                        temp_check_out = False
                                        temp_time1 = datetime.strptime(
                                            str(check_record.check_in),
                                            "%Y-%m-%d %H:%M:%S",
                                        ).astimezone(pytz.timezone("Asia/Karachi"))
                                        temp_time1 = datetime.strptime(
                                            str(temp_time1),
                                            "%Y-%m-%d %H:%M:%S+05:00",
                                        )
                                        print("Exist Time: ", temp_time1)
                                        if temp_time1 > temp_time:
                                            if len(check_record.timeoff_id) == 0:
                                                if margin_shift_start <= temp_time < present_end:
                                                    check_record.check_in_status = "presentontime"
                                                    check_record.status_leave = "present"
                                                    check_record.late_time = False
                                                    # print(
                                                    #     "Exist Status: Present"
                                                    # )
                                                elif present_end <= temp_time < late_end:
                                                    check_record.check_in_status = "late"
                                                    check_record.status_leave = "late"
                                                    check_record.late_time = str(temp_time - shift_start)
                                                    # print(
                                                    #     "Exist Status: Late"
                                                    # )
                                                elif late_end <= temp_time < short_end:
                                                    check_record.check_in_status = "shortleave"
                                                    check_record.status_leave = "shortleave_paid"
                                                    check_record.late_time = str(temp_time - shift_start)
                                                    # print(
                                                    #     "Exist Status: ShortLeave"
                                                    # )
                                            temp1 = check_record.check_in
                                            check_record.check_in = atten_time
                                            check_record.check_out = temp1
                                            temp_check_out = True
                                        else:
                                            if shift_end > temp_time >= present_end:
                                                temp_time1 = datetime.strptime(
                                                    str(check_record.check_out),
                                                    "%Y-%m-%d %H:%M:%S",
                                                ).astimezone(pytz.timezone("Asia/Karachi"))
                                                temp_time1 = datetime.strptime(
                                                    str(temp_time1),
                                                    "%Y-%m-%d %H:%M:%S+05:00",
                                                )
                                                if temp_time1 < temp_time:
                                                    check_record.check_out = atten_time
                                                    temp_check_out = True
                                        if temp_check_out:
                                            temp_time = datetime.strptime(
                                                str(check_record.check_out),
                                                "%Y-%m-%d %H:%M:%S",
                                            ).astimezone(pytz.timezone("Asia/Karachi"))
                                            temp_time = datetime.strptime(
                                                str(temp_time),
                                                "%Y-%m-%d %H:%M:%S+05:00",
                                            )
                                            if len(
                                                check_record.timeoff_id1
                                            ) == 0 and check_record.check_out_status not in (
                                                "casualleave",
                                                "paidleave",
                                                "unpaidleave",
                                                "outdoorduty",
                                                "workfromhome",
                                                "sickleave",
                                                "compensatoryleave",
                                                "gazetteleave",
                                                "officialleaves",
                                            ):
                                                rest_day = employee_id.rest_days_ids.mapped("name")
                                                date_check1 = temp_time.date()
                                                if date_check1.strftime("%A") in rest_day:
                                                    check_record.early_time = False
                                                    check_record.check_out_status = "presentontime"
                                                elif shift_late_departure_margin <= temp_time:
                                                    check_record.early_time = False
                                                    check_record.check_out_status = "presentontime"
                                                elif (
                                                    shift_late_departure_margin
                                                    > temp_time
                                                    >= shift_late_departure
                                                ):
                                                    check_record.early_time = str(shift_close - temp_time)
                                                    check_record.check_out_status = "late"
                                                elif (
                                                    shift_late_departure
                                                    > temp_time
                                                    >= shift_short_departure
                                                ):
                                                    check_record.early_time = str(shift_close - temp_time)
                                                    check_record.check_out_status = "shortleave"
                                                else:
                                                    check_record.early_time = str(shift_close - temp_time)
                                                    if check_record.check_out_status == "halfleave":
                                                        check_record.check_out_status = "halfleave"
                                                    else:
                                                        check_record.check_out_status = "absent"

                                    # print(
                                    #     {
                                    #         "employee_id": employee_id.id,
                                    #         "device_id_num": each.user_id,
                                    #         "punching_day": timendate[0],
                                    #         "attendance_type": str(each.status),
                                    #         "location_device": str(machine_ip),
                                    #         "punching_time": atten_time,
                                    #     }
                                    # )
                                    zk_attendance.create(
                                        {
                                            "employee_id": employee_id.id,
                                            "device_id_num": each.user_id,
                                            "punching_day": timendate[0],
                                            "attendance_type": str(each.status),
                                            "location_device": str(machine_ip),
                                            "punching_time": atten_time,
                                        }
                                    )
                                    # print(
                                    #     "------------------------------------------------------------------\n"
                                    # )

    def action_receive_punches(self, punches):
        """Receive attendance punches pushed remotely from a local agent
        script running on the same LAN as the biometric device (used when
        Odoo itself, e.g. on odoo.sh, cannot reach the device directly).

        The punches are converted into real pyzk ``Attendance`` objects and
        run through ``_process_attendance_batch`` — the exact same
        shift-based check-in/check-out logic used by
        ``action_download_attendance`` when Odoo pulls directly from the
        device on localhost. This keeps behaviour identical between the two
        paths.

        :param punches: list of dicts, each like:
            {'device_id_num': '23', 'timestamp': '2026-07-27 08:31:05', 'status': 1}
            timestamp must be the RAW device-local naive datetime string
            '%Y-%m-%d %H:%M:%S' (do NOT pre-convert to UTC — the shared
            processing logic performs that conversion itself, using the
            Odoo user's timezone, exactly as it does for a local pull).
            'status' is optional (pyzk's punch status code); defaults to 1.
        :return: dict summary of how many punches were received / matched.
        """
        for info in self:
            machine_ip = info.device_ip
            attendances = []
            unmatched_timestamps = 0
            for punch in punches:
                device_id_num = str(punch.get("device_id_num"))
                timestamp_str = punch.get("timestamp")
                if not device_id_num or not timestamp_str:
                    unmatched_timestamps += 1
                    continue
                try:
                    punch_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    unmatched_timestamps += 1
                    continue
                attendances.append(
                    Attendance(
                        user_id=device_id_num,
                        timestamp=punch_dt,
                        status=punch.get("status", 1),
                    )
                )

            if attendances:
                self._process_attendance_batch(info, machine_ip, attendances)

            _logger.info(
                "ZK Agent push: %s punches received, %s malformed/skipped",
                len(attendances), unmatched_timestamps,
            )
            return {
                "received": len(attendances),
                "malformed": unmatched_timestamps,
            }

    def action_download_attendance(self):
        """Function to download attendance records from the device"""
        _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
        zk_attendance = self.env["zk.machine.attendance"]
        hr_attendance = self.env["hr.attendance"]
        for info in self:
            machine_ip = info.device_ip
            zk_port = info.port_number
            try:
                # Connecting with the device with the IP and port provided
                zk = ZK(
                    machine_ip,
                    port=zk_port,
                    timeout=15,
                    password=0,
                    force_udp=False,
                    ommit_ping=False,
                )
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            try:
                conn = self.device_connect(zk)
                # print(conn)
                if conn:
                    conn.disable_device()  # Device cannot be used during this time.
                    users = conn.get_users()
                    attendances = conn.get_attendance()
                    # print(attendance)
                    self._process_attendance_batch(info, machine_ip, attendances)
                    print("Attendance Downloaded Successfully")
                    conn.enable_device()
                    conn.disconnect()
            except Exception as e:
                _logger.error("Process terminated: {}".format(e))

    def action_get_data(self):
        res = self.env["biometric.device.details"].search([])
        for info in res:
            machine_ip = info.device_ip
            zk_port = info.port_number
            conn = None
            device_data = []
            biometric_data_model = self.env["biometic.machine.data"]
            try:
                # Connecting with the device with the IP and port provided
                zk = ZK(
                    machine_ip,
                    port=zk_port,
                    timeout=15,
                    password=0,
                    force_udp=False,
                    ommit_ping=False,
                )
                conn = zk.connect()
                # Fetching the attendance data from the device
                users = conn.get_users()
                for user in users:
                    privilege = "User"
                    if user.privilege == const.USER_ADMIN:
                        privilege = "Admin"
                    # print("Uid: %s" % user.uid)
                    # print("Privilege: %s" % privilege)
                    # print("password: %s" % user.password)
                    # print("group_id: %s" % user.group_id)
                    # print("User ID: %s" % user.user_id)
                    # print("employee_name: %s" % user.name)
                    exisiting_record = biometric_data_model.search(
                        [("user_id", "=", user.user_id), ("user_machine_id", "=", info.id)]
                    ).exists()
                    if not exisiting_record:
                        device_data.append(
                            {
                                "uid": user.uid or "N/A",
                                "group_id": user.group_id or "N/A",
                                "card": user.card or "N/A",
                                "employee_name": user.name or "N/A",
                                "password": user.password or "N/A",
                                "user_id": user.user_id or "N/A",
                                "user_machine_id": info.id,
                                "name": info.name or "N/A",
                                "privilege": privilege or "N/A",
                            }
                        )
                    # print("------------------")
                print("Machine IP: %s" % info.name)
                print("Machine serial: %s" % conn.get_serialnumber())
                if not info.serial_no:
                    info.serial_no = conn.get_serialnumber()
                # print(device_data)
                if device_data:
                    biometric_data_model.sudo().create(device_data)
                conn.enable_device()
            except Exception as e:
                _logger.error("Error in connecting to the device: %s" % e)
            finally:
                if conn:
                    conn.disconnect()
        return True

    # def action_download_attendance(self):
    #     """Function to download attendance records from the device"""
    #     _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
    #     zk_attendance = self.env["zk.machine.attendance"]
    #     hr_attendance = self.env["hr.attendance"]
    #     for info in self:
    #         machine_ip = info.device_ip
    #         zk_port = info.port_number
    #         try:
    #             # Connecting with the device with the IP and port provided
    #             zk = ZK(
    #                 machine_ip,
    #                 port=zk_port,
    #                 timeout=15,
    #                 password=0,
    #                 force_udp=False,
    #                 ommit_ping=False,
    #             )
    #         except employee_idError:
    #             raise UserError(
    #                 _(
    #                     "Pyzk module not Found. Please install it with 'pip3 install pyzk'."
    #                 )
    #             )
    #         try:
    #             conn = self.device_connect(zk)
    #             if conn:
    #                 conn.disable_device()  # Device cannot be used during this time.
    #                 users = conn.get_users()
    #                 attendances = conn.get_attendance()
    #                 today = datetime.datetime.today().date()
    #                 date_start = datetime.date(2024, 5, 1)
    #                 todays_attendance = [
    #                     each
    #                     for each in attendances
    #                     if each.timestamp.date() >= date_start
    #                 ]

    #                 if todays_attendance:
    #                     for each in todays_attendance:
    #                         atten_time = each.timestamp
    #                         local_tz = pytz.timezone(
    #                             self.env.user.partner_id.tz or "GMT"
    #                         )
    #                         local_dt = local_tz.localize(atten_time, is_dst=None)
    #                         utc_dt = local_dt.astimezone(pytz.utc)
    #                         utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    #                         atten_time = datetime.datetime.strptime(
    #                             utc_dt, "%Y-%m-%d %H:%M:%S"
    #                         )
    #                         atten_time = fields.Datetime.to_string(atten_time)
    #                         temp_atten_time = fields.Datetime.from_string(atten_time)

    #                         for user in users:

    #                             if (
    #                                 user.user_id == each.user_id
    #                                 and each.user_id == "1876"
    #                             ):

    #                                 get_user_id = self.env["hr.employee"].search(
    #                                     [("device_id_num", "=", each.user_id)]
    #                                 )
    #                                 if get_user_id:
    #                                     duplicate_atten_ids = zk_attendance.search(
    #                                         [
    #                                             ("device_id_num", "=", each.user_id),
    #                                             ("punching_time", "=", atten_time),
    #                                         ]
    #                                     )
    #                                     if not duplicate_atten_ids:

    #                                         zk_attendance.create(
    #                                             {
    #                                                 "employee_id": get_user_id.id,
    #                                                 "device_id_num": each.user_id,
    #                                                 "attendance_type": str(each.status),
    #                                                 "punch_type": str(each.punch),
    #                                                 "punching_time": atten_time,
    #                                                 "address_id": info.address_id.id,
    #                                             }
    #                                         )
    #                                         # Fetch the employee's shift times
    #                                         shift_start = (
    #                                             get_user_id.resource_calendar_id.shift_start
    #                                         )
    #                                         shift_end = (
    #                                             get_user_id.resource_calendar_id.shift_end
    #                                         )

    #                                         # Convert shift times to datetime
    #                                         shift_start_time = (
    #                                             datetime.datetime.combine(
    #                                                 temp_atten_time.date(),
    #                                                 datetime.time(
    #                                                     int(shift_start),
    #                                                     int((shift_start % 1) * 60),
    #                                                 ),
    #                                             )
    #                                         )
    #                                         shift_end_time = datetime.datetime.combine(
    #                                             temp_atten_time.date(),
    #                                             datetime.time(
    #                                                 int(shift_end),
    #                                                 int((shift_end % 1) * 60),
    #                                             ),
    #                                         )

    #                                         if (
    #                                             shift_start_time
    #                                             <= temp_atten_time
    #                                             <= shift_end_time
    #                                         ):
    #                                             # Determine if the attendance time is closer to shift start or shift end
    #                                             mid_shift_time = (
    #                                                 shift_start_time
    #                                                 + (
    #                                                     shift_end_time
    #                                                     - shift_start_time
    #                                                 )
    #                                                 / 2
    #                                             )

    #                                             if temp_atten_time <= mid_shift_time:
    #                                                 # Closer to shift start, treat as check-in
    #                                                 existing_checkin = (
    #                                                     hr_attendance.search(
    #                                                         [
    #                                                             (
    #                                                                 "employee_id",
    #                                                                 "=",
    #                                                                 get_user_id.id,
    #                                                             ),
    #                                                             (
    #                                                                 "check_in",
    #                                                                 ">=",
    #                                                                 shift_start_time,
    #                                                             ),
    #                                                             (
    #                                                                 "check_in",
    #                                                                 "<=",
    #                                                                 shift_end_time,
    #                                                             ),
    #                                                         ]
    #                                                     )
    #                                                 )
    #                                                 if not existing_checkin:
    #                                                     hr_attendance.create(
    #                                                         {
    #                                                             "employee_id": get_user_id.id,
    #                                                             "check_in": atten_time,
    #                                                         }
    #                                                     )
    #                                             else:
    #                                                 # Closer to shift end, treat as check-out
    #                                                 att_var = hr_attendance.search(
    #                                                     [
    #                                                         (
    #                                                             "employee_id",
    #                                                             "=",
    #                                                             get_user_id.id,
    #                                                         ),
    #                                                         ("check_out", "=", False),
    #                                                     ]
    #                                                 )
    #                                                 if len(att_var) == 1:
    #                                                     att_var.write(
    #                                                         {"check_out": atten_time}
    #                                                     )
    #                                                 elif len(att_var) == 0:
    #                                                     hr_attendance.create(
    #                                                         {
    #                                                             "employee_id": get_user_id.id,
    #                                                             "check_in": shift_start_time,
    #                                                             "check_out": atten_time,
    #                                                         }
    #                                                     )

    #                 # Handling missed check-ins or check-outs for the day
    #                 for employee in self.env["hr.employee"].search([]):
    #                     # Fetch the employee's shift times
    #                     shift_start = employee.resource_calendar_id.shift_start
    #                     shift_end = employee.resource_calendar_id.shift_end

    #                     shift_start_time = datetime.datetime.combine(
    #                         today,
    #                         datetime.time(
    #                             int(shift_start), int((shift_start % 1) * 60)
    #                         ),
    #                     )
    #                     shift_end_time = datetime.datetime.combine(
    #                         today,
    #                         datetime.time(int(shift_end), int((shift_end % 1) * 60)),
    #                     )

    #                     employee_attendance = hr_attendance.search(
    #                         [
    #                             ("employee_id", "=", employee.id),
    #                             (
    #                                 "check_in",
    #                                 ">=",
    #                                 self._convert_date(
    #                                     datetime.datetime.combine(
    #                                         today, datetime.time.min
    #                                     )
    #                                 ),
    #                             ),
    #                             (
    #                                 "check_out",
    #                                 "<=",
    #                                 self._convert_date(
    #                                     datetime.datetime.combine(
    #                                         today, datetime.time.max
    #                                     ),
    #                                 ),
    #                             ),
    #                         ]
    #                     )
    #                     if not employee_attendance:
    #                         hr_attendance.create(
    #                             {
    #                                 "employee_id": employee.id,
    #                                 "check_in": shift_start_time,
    #                                 "check_out": shift_end_time,
    #                                 # "attendance_type": "missed",
    #                             }
    #                         )

    #                 conn.enable_device()
    #         except Exception as e:
    #             _logger.error("Process terminated: {}".format(e))
    #         finally:
    #             conn.disconnect()

    # def action_download_attendance(self):
    #     """Function to download attendance records from the device"""
    #     _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
    #     zk_attendance = self.env["zk.machine.attendance"]
    #     hr_attendance = self.env["hr.attendance"]
    #     for info in self:
    #         machine_ip = info.device_ip
    #         zk_port = info.port_number
    #         try:
    #             # Connecting with the device with the ip and port provided
    #             zk = ZK(
    #                 machine_ip,
    #                 port=zk_port,
    #                 timeout=15,
    #                 password=0,
    #                 force_udp=False,
    #                 ommit_ping=False,
    #             )
    #         except employee_idError:
    #             raise UserError(
    #                 _(
    #                     "Pyzk module not Found. Please install it"
    #                     "with 'pip3 install pyzk'."
    #                 )
    #             )
    #         try:
    #             conn = self.device_connect(zk)
    #             if conn:
    #                 conn.disable_device()  # Device Cannot be used during this time.
    #                 user = conn.get_users()
    #                 attendance = conn.get_attendance()
    #                 print(type(attendance))
    #                 today = datetime.datetime.today().date()
    #                 date_start = datetime.date(2024, 5, 25)
    #                 todays_attendance = [
    #                     each
    #                     for each in attendance
    #                     if each.timestamp.date() >= date_start
    #                 ]

    #                 if todays_attendance:
    #                     # print(attendance)
    #                     # break
    #                     for each in todays_attendance:
    #                         atten_time = each.timestamp
    #                         local_tz = pytz.timezone(
    #                             self.env.user.partner_id.tz or "GMT"
    #                         )
    #                         local_dt = local_tz.localize(atten_time, is_dst=None)
    #                         utc_dt = local_dt.astimezone(pytz.utc)
    #                         utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    #                         atten_time = datetime.datetime.strptime(
    #                             utc_dt, "%Y-%m-%d %H:%M:%S"
    #                         )
    #                         atten_time = fields.Datetime.to_string(atten_time)
    #                         temp_atten_time = fields.Datetime.from_string(atten_time)
    #                         # print(atten_time)
    #                         # break
    #                         for uid in user:
    #                             get_user_id = False
    #                             if (
    #                                 uid.user_id == "1876"
    #                                 or uid.user_id == "1947"
    #                                 or uid.user_id == "1930"
    #                             ):
    #                                 get_user_id = self.env["hr.employee"].search(
    #                                     [("device_id_num", "=", each.user_id)]
    #                                 )
    #                             if uid.user_id == each.user_id and get_user_id:

    #                                 # print(each)
    #                                 if get_user_id:
    #                                     # print(get_user_id.employee_id)
    #                                     duplicate_atten_ids = zk_attendance.search(
    #                                         [
    #                                             ("device_id_num", "=", each.user_id),
    #                                             ("punching_time", "=", atten_time),
    #                                         ]
    #                                     )
    #                                     shift_start = (
    #                                         get_user_id.resource_calendar_id.shift_start
    #                                     )
    #                                     shift_end = (
    #                                         get_user_id.resource_calendar_id.shift_end
    #                                     )
    #                                     # Convert float time to datetime.time
    #                                     shift_start_time = datetime.time(
    #                                         int(shift_start),
    #                                         int((shift_start % 1) * 60),
    #                                     )
    #                                     shift_end_time = datetime.time(
    #                                         int(shift_end), int((shift_end % 1) * 60)
    #                                     )
    #                                     # Combine date and time to get datetime
    #                                     shift_start_datetime = (
    #                                         datetime.datetime.combine(
    #                                             temp_atten_time.date(), shift_start_time
    #                                         )
    #                                     )
    #                                     shift_end_datetime = datetime.datetime.combine(
    #                                         temp_atten_time.date(), shift_end_time
    #                                     )
    #                                     print("=====================================")
    #                                     print("User ID", each.user_id)
    #                                     print("employee_id", get_user_id.employee_id)
    #                                     print("Device ID", each.user_id)
    #                                     print("Attendance Type", each.status)
    #                                     print("Punch Type", each.punch)
    #                                     print("Punching Old", each.timestamp)
    #                                     print("Punching Time", atten_time)
    #                                     print("Punching Date", temp_atten_time.date())
    #                                     print("Address ID", info.address_id.id)
    #                                     print("tmep date ", temp_atten_time)
    #                                     print("Shift Start Time", shift_start_datetime)
    #                                     print("Shift End Time", shift_end_datetime)
    #                                     print("=====================================")

    #                                     if not duplicate_atten_ids:

    #                                         zk_attendance.create(
    #                                             {
    #                                                 "employee_id": get_user_id.id,
    #                                                 "device_id_num": each.user_id,
    #                                                 "attendance_type": str(each.status),
    #                                                 "punch_type": str(each.punch),
    #                                                 "punching_time": atten_time,
    #                                                 "address_id": info.address_id.id,
    #                                             }
    #                                         )
    #                                         att_var = hr_attendance.search(
    #                                             [
    #                                                 (
    #                                                     "employee_id",
    #                                                     "=",
    #                                                     get_user_id.id,
    #                                                 ),
    #                                                 ("check_out", "=", False),
    #                                             ]
    #                                         )
    #                                         if each.punch == 0:
    #                                             # check-in
    #                                             existing_checkin = hr_attendance.search(
    #                                                 [
    #                                                     (
    #                                                         "employee_id",
    #                                                         "=",
    #                                                         get_user_id.id,
    #                                                     ),
    #                                                     (
    #                                                         "check_in",
    #                                                         ">=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.min.time(),
    #                                                         ),
    #                                                     ),
    #                                                     (
    #                                                         "check_in",
    #                                                         "<=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.max.time(),
    #                                                         ),
    #                                                     ),
    #                                                 ]
    #                                             )
    #                                             print(
    #                                                 "Existing Checkin", existing_checkin
    #                                             )
    #                                             if not existing_checkin and not att_var:
    #                                                 hr_attendance.create(
    #                                                     {
    #                                                         "employee_id": get_user_id.id,
    #                                                         "check_in": atten_time,
    #                                                     }
    #                                                 )
    #                                         if each.punch == 1:  # check-out
    #                                             existing_checkout = hr_attendance.search(
    #                                                 [
    #                                                     (
    #                                                         "employee_id",
    #                                                         "=",
    #                                                         get_user_id.id,
    #                                                     ),
    #                                                     (
    #                                                         "check_out",
    #                                                         ">=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.min.time(),
    #                                                         ),
    #                                                     ),
    #                                                     (
    #                                                         "check_out",
    #                                                         "<=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.max.time(),
    #                                                         ),
    #                                                     ),
    #                                                 ]
    #                                             )
    #                                             if (
    #                                                 not existing_checkout
    #                                                 and len(att_var) == 1
    #                                             ):
    #                                                 att_var.write(
    #                                                     {"check_out": atten_time}
    #                                                 )
    #                                             elif (
    #                                                 not existing_checkout
    #                                                 and len(att_var) == 0
    #                                             ):

    #                                                 if each.timestamp.date() != today:
    #                                                     check_in_time = datetime.datetime.combine(
    #                                                         temp_atten_time.date(),
    #                                                         datetime.datetime.min.time(),
    #                                                     )

    #                                                     check_in_time = (
    #                                                         self._convert_date(
    #                                                             check_in_time
    #                                                         )
    #                                                     )
    #                                                     hr_attendance.create(
    #                                                         {
    #                                                             "employee_id": get_user_id.id,
    #                                                             "check_in": check_in_time,
    #                                                             "check_out": atten_time,
    #                                                         }
    #                                                     )
    #                                                 if each.timestamp.date() == today:
    #                                                     hr_attendance.create(
    #                                                         {
    #                                                             "employee_id": get_user_id.id,
    #                                                             "check_in": atten_time,
    #                                                         }
    #                                                     )

    #                                         if (
    #                                             each.punch == 0
    #                                             and len(att_var) == 1
    #                                             and not att_var.check_out
    #                                         ):
    #                                             if each.timestamp.date() != today:
    #                                                 check_out_time = datetime.datetime.combine(
    #                                                     temp_atten_time.date(),
    #                                                     datetime.datetime.max.time(),
    #                                                 )

    #                                                 check_out_time = self._convert_date(
    #                                                     check_out_time
    #                                                 )

    #                                                 print(
    #                                                     "Check Out Time", check_out_time
    #                                                 )
    #                                                 att_var.write(
    #                                                     {"check_out": check_out_time}
    #                                                 )
    #                                             else:

    #                                                 hr_attendance.create(
    #                                                     {
    #                                                         "employee_id": get_user_id.id,
    #                                                         "check_in": atten_time,
    #                                                     }
    #                                                 )

    #                                             # check_out_time = (
    #                                             #     datetime.datetime.combine(
    #                                             #         temp_atten_time.date(),
    #                                             #         datetime.datetime.max.time(),
    #                                             #     )
    #                                             # )

    #                                             # check_out_time = self._convert_date(
    #                                             #     check_out_time
    #                                             # )

    #                                             # print("Check Out Time", check_out_time)
    #                                             # att_var.write(
    #                                             #     {"check_out": check_out_time}
    #                                             # )

    #                             else:
    #                                 # check-out
    #                                 continue
    #                     print("Attendance Downloaded Successfully")
    #                     conn.disconnect()
    #                     return True
    #                 else:
    #                     raise UserError(
    #                         _(
    #                             "Unable to get the attendance log, please"
    #                             "try again later."
    #                         )
    #                     )
    #             else:
    #                 raise UserError(
    #                     _(
    #                         "Unable to connect, please check the"
    #                         "parameters and network connections."
    #                     )
    #                 )
    #         except Exception as error:
    #             raise ValidationError(f"{error}")

    # finally:
    #     if conn:
    #         zk.disconnect()
    # def action_download_attendance(self):
    #     """Function to download attendance records from the device"""
    #     _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
    #     zk_attendance = self.env["zk.machine.attendance"]
    #     hr_attendance = self.env["hr.attendance"]
    #     for info in self:
    #         machine_ip = info.device_ip
    #         zk_port = info.port_number
    #         try:
    #             # Connecting with the device with the ip and port provided
    #             zk = ZK(
    #                 machine_ip,
    #                 port=zk_port,
    #                 timeout=15,
    #                 password=0,
    #                 force_udp=False,
    #                 ommit_ping=False,
    #             )
    #         except employee_idError:
    #             raise UserError(
    #                 _(
    #                     "Pyzk module not Found. Please install it"
    #                     "with 'pip3 install pyzk'."
    #                 )
    #             )
    #         try:
    #             conn = self.device_connect(zk)
    #             if conn:
    #                 conn.disable_device()  # Device Cannot be used during this time.
    #                 user = conn.get_users()
    #                 attendance = conn.get_attendance()
    #                 today = datetime.datetime.today().date()
    #                 date_start = datetime.date(2024, 5, 25)
    #                 todays_attendance = [
    #                     each
    #                     for each in attendance
    #                     if each.timestamp.date() >= date_start
    #                 ]

    #                 if todays_attendance:
    #                     for each in todays_attendance:
    #                         atten_time = each.timestamp
    #                         local_tz = pytz.timezone(
    #                             self.env.user.partner_id.tz or "GMT"
    #                         )
    #                         local_dt = local_tz.localize(atten_time, is_dst=None)
    #                         utc_dt = local_dt.astimezone(pytz.utc)
    #                         utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    #                         atten_time = datetime.datetime.strptime(
    #                             utc_dt, "%Y-%m-%d %H:%M:%S"
    #                         )
    #                         atten_time = fields.Datetime.to_string(atten_time)
    #                         temp_atten_time = fields.Datetime.from_string(atten_time)

    #                         for uid in user:
    #                             get_user_id = False
    #                             if (
    #                                 uid.user_id == "1876"
    #                                 or uid.user_id == "1947"
    #                                 or uid.user_id == "1930"
    #                             ):
    #                                 get_user_id = self.env["hr.employee"].search(
    #                                     [("device_id_num", "=", each.user_id)]
    #                                 )
    #                             if uid.user_id == each.user_id and get_user_id:
    #                                 if get_user_id:
    #                                     duplicate_atten_ids = zk_attendance.search(
    #                                         [
    #                                             ("device_id_num", "=", each.user_id),
    #                                             ("punching_time", "=", atten_time),
    #                                         ]
    #                                     )
    #                                     shift_start = (
    #                                         get_user_id.resource_calendar_id.shift_start
    #                                     )
    #                                     shift_end = (
    #                                         get_user_id.resource_calendar_id.shift_end
    #                                     )
    #                                     shift_start_time = datetime.time(
    #                                         int(shift_start),
    #                                         int((shift_start % 1) * 60),
    #                                     )
    #                                     shift_end_time = datetime.time(
    #                                         int(shift_end), int((shift_end % 1) * 60)
    #                                     )
    #                                     shift_start_datetime = (
    #                                         datetime.datetime.combine(
    #                                             temp_atten_time.date(), shift_start_time
    #                                         )
    #                                     )
    #                                     shift_end_datetime = datetime.datetime.combine(
    #                                         temp_atten_time.date(), shift_end_time
    #                                     )
    #                                     print("=====================================")
    #                                     print("User ID", each.user_id)
    #                                     print("employee_id", get_user_id.employee_id)
    #                                     print("Device ID", each.user_id)
    #                                     print("Attendance Type", each.status)
    #                                     print("Punch Type", each.punch)
    #                                     print("Punching Old", each.timestamp)
    #                                     print("Punching Time", atten_time)
    #                                     print("Punching Date", temp_atten_time.date())
    #                                     print("Address ID", info.address_id.id)
    #                                     print("tmep date ", temp_atten_time)
    #                                     print("Shift Start Time", shift_start_datetime)
    #                                     print("Shift End Time", shift_end_datetime)
    #                                     print("=====================================")
    #                                     if not duplicate_atten_ids:
    #                                         zk_attendance.create(
    #                                             {
    #                                                 "employee_id": get_user_id.id,
    #                                                 "device_id_num": each.user_id,
    #                                                 "attendance_type": str(each.status),
    #                                                 "punch_type": str(each.punch),
    #                                                 "punching_time": atten_time,
    #                                                 "address_id": info.address_id.id,
    #                                             }
    #                                         )
    #                                         att_var = hr_attendance.search(
    #                                             [
    #                                                 (
    #                                                     "employee_id",
    #                                                     "=",
    #                                                     get_user_id.id,
    #                                                 ),
    #                                                 ("check_out", "=", False),
    #                                             ]
    #                                         )

    #                                         if abs(
    #                                             (
    #                                                 temp_atten_time
    #                                                 - shift_start_datetime
    #                                             ).total_seconds()
    #                                         ) < abs(
    #                                             (
    #                                                 temp_atten_time - shift_end_datetime
    #                                             ).total_seconds()
    #                                         ):
    #                                             # Check-in
    #                                             existing_checkin = hr_attendance.search(
    #                                                 [
    #                                                     (
    #                                                         "employee_id",
    #                                                         "=",
    #                                                         get_user_id.id,
    #                                                     ),
    #                                                     (
    #                                                         "check_in",
    #                                                         ">=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.min.time(),
    #                                                         ),
    #                                                     ),
    #                                                     (
    #                                                         "check_in",
    #                                                         "<=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.max.time(),
    #                                                         ),
    #                                                     ),
    #                                                 ]
    #                                             )
    #                                             if not existing_checkin and not att_var:
    #                                                 hr_attendance.create(
    #                                                     {
    #                                                         "employee_id": get_user_id.id,
    #                                                         "check_in": atten_time,
    #                                                     }
    #                                                 )
    #                                         else:
    #                                             # Check-out
    #                                             existing_checkout = hr_attendance.search(
    #                                                 [
    #                                                     (
    #                                                         "employee_id",
    #                                                         "=",
    #                                                         get_user_id.id,
    #                                                     ),
    #                                                     (
    #                                                         "check_out",
    #                                                         ">=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.min.time(),
    #                                                         ),
    #                                                     ),
    #                                                     (
    #                                                         "check_out",
    #                                                         "<=",
    #                                                         datetime.datetime.combine(
    #                                                             temp_atten_time.date(),
    #                                                             datetime.datetime.max.time(),
    #                                                         ),
    #                                                     ),
    #                                                 ]
    #                                             )
    #                                             if (
    #                                                 not existing_checkout
    #                                                 and len(att_var) == 1
    #                                             ):
    #                                                 att_var.write(
    #                                                     {"check_out": atten_time}
    #                                                 )
    #                                             elif (
    #                                                 not existing_checkout
    #                                                 and len(att_var) == 0
    #                                             ):
    #                                                 if each.timestamp.date() != today:
    #                                                     check_in_time = datetime.datetime.combine(
    #                                                         temp_atten_time.date(),
    #                                                         datetime.datetime.min.time(),
    #                                                     )

    #                                                     check_in_time = (
    #                                                         self._convert_date(
    #                                                             check_in_time
    #                                                         )
    #                                                     )
    #                                                     hr_attendance.create(
    #                                                         {
    #                                                             "employee_id": get_user_id.id,
    #                                                             "check_in": check_in_time,
    #                                                             "check_out": atten_time,
    #                                                         }
    #                                                     )
    #                                                 if each.timestamp.date() == today:
    #                                                     hr_attendance.create(
    #                                                         {
    #                                                             "employee_id": get_user_id.id,
    #                                                             "check_in": atten_time,
    #                                                         }
    #                                                     )

    #                                         if (
    #                                             each.punch == 0
    #                                             and len(att_var) == 1
    #                                             and not att_var.check_out
    #                                         ):
    #                                             if each.timestamp.date() != today:
    #                                                 check_out_time = datetime.datetime.combine(
    #                                                     temp_atten_time.date(),
    #                                                     datetime.datetime.max.time(),
    #                                                 )

    #                                                 check_out_time = self._convert_date(
    #                                                     check_out_time
    #                                                 )
    #                                                 att_var.write(
    #                                                     {"check_out": check_out_time}
    #                                                 )
    #                                             else:
    #                                                 hr_attendance.create(
    #                                                     {
    #                                                         "employee_id": get_user_id.id,
    #                                                         "check_in": atten_time,
    #                                                     }
    #                                                 )
    #                                 else:
    #                                     continue
    #                     print("Attendance Downloaded Successfully")
    #                     conn.disconnect()

    #                     return True
    #                 else:
    #                     raise UserError(
    #                         _(
    #                             "Unable to get the attendance log, please"
    #                             "try again later."
    #                         )
    #                     )
    #             else:
    #                 raise UserError(
    #                     _(
    #                         "Unable to connect, please check the"
    #                         "parameters and network connections."
    #                     )
    #                 )
    #         except Exception as error:
    #             raise ValidationError(f"{error}")

    def _convert_date(self, date):
        """Function to convert the date"""
        local_tz = pytz.timezone(self.env.user.partner_id.tz or "GMT")
        local_dt = local_tz.localize(date, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.utc)
        utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
        atten_time = datetime.datetime.strptime(utc_dt, "%Y-%m-%d %H:%M:%S")
        atten_time = fields.Datetime.to_string(atten_time)
        return atten_time

    def action_restart_device(self):
        """For restarting the device"""
        zk = ZK(
            self.device_ip,
            port=self.port_number,
            timeout=15,
            password=0,
            force_udp=False,
            ommit_ping=False,
        )
        self.device_connect(zk).restart()