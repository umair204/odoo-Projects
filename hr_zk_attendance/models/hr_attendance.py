# -*- coding: utf-8 -*-
import logging
from datetime import timedelta, datetime, date
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = "hr.attendance"
    employee_code = fields.Char(related="employee_id.device_id_num", tracking=True, readonly=True)
    check_in_status = fields.Selection(
        selection=[
            ("presentontime", "Present"),
            ("late", "Late"),
            ("shortleave", "Short Leave"),
            ("halfleave", "Half Leave"),
            ("restday", "Rest Day"),
            ("paidleave", "Paid Leave"),
            ("unpaidleave", "Unpaid Leave"),
            ("casualleave", "Casual Leave"),
            ("sickleave", "Sick Leave"),
            ("compensatoryleave", "Compensatory Leave"),
            ("gazetteleave", "Gazette Leave"),
            ("officialleaves", "Official Leave"),
            ("workfromhome", "Work from Home"),
            ("outdoorduty", "Outdoor Duty"),
            ("absent", "Absent"),
        ],
        string="Check In Status",
        tracking=True,
        store=True,
        readonly=False,
    )
    check_out_status = fields.Selection(
        selection=[
            ("presentontime", "Present"),
            ("late", "Late"),
            ("shortleave", "Short Leave"),
            ("halfleave", "Half Leave"),
            ("restday", "Rest Day"),
            ("paidleave", "Paid Leave"),
            ("unpaidleave", "Unpaid Leave"),
            ("casualleave", "Casual Leave"),
            ("sickleave", "Sick Leave"),
            ("compensatoryleave", "Compensatory Leave"),
            ("gazetteleave", "Gazette Leave"),
            ("officialleaves", "Official Leave"),
            ("workfromhome", "Work from Home"),
            ("outdoorduty", "Outdoor Duty"),
            ("absent", "Absent"),
        ],
        string="Check Out Status",
        tracking=True,
        store=True,
        readonly=False,
    )
    is_absent = fields.Boolean("Is Absent")
    late_time = fields.Char(string="Late Check In", tracking=True, readonly=False)
    early_time = fields.Char(string="Early Check Out", tracking=True, readonly=False)
    employee_shift_id = fields.Many2one("employee.shift", string="Employee Shift")
    status_leave = fields.Selection(
        selection=[
            ("present", "Present"),
            ("late", "Late"),
            ("shortleave_unpaid", "Short Leave Unpaid"),
            ("shortleave_paid", "Short Leave Paid"),
            ("halfleave_unpaid", "Half Leave Unpaid"),
            ("halfleave_paid", "Half Leave Paid"),
            ("restday", "Rest Day"),
            ("paidleave", "Paid Leave"),
            ("unpaidleave", "Unpaid Leave"),
            ("casualleave", "Casual Leave"),
            ("sickleave", "Sick Leave"),
            ("compensatoryleave", "Compensatory Leave"),
            ("gazetteleave", "Gazette Leave"),
            ("officialleaves", "Official Leave"),
            ("workfromhome", "Work from Home"),
            ("absent", "Absent"),
        ],
        string="Leave Status",
        tracking=False,
        store=True,
        readonly=False,
    )
    current_shift_att_date = fields.Date(string="Current Shift Date", tracking=True)
    current_shift_day = fields.Char(string="Current Shift Day", tracking=True, compute="_compute_current_shift_day")

    @api.depends("current_shift_att_date")
    def _compute_current_shift_day(self):
        for rec in self:
            if rec.current_shift_att_date:
                rec.current_shift_day = rec.current_shift_att_date.strftime("%A")
            else:
                rec.current_shift_day = False

    timeoff_id1 = fields.Many2one("hr.leave", string="TimeOff Ref 2nd")
    timeoff_id = fields.Many2one("hr.leave", string="TimeOff Ref")
    department_id = fields.Many2one(
        "hr.department", string="Department", related="employee_id.department_id", readonly=True, store=True
    )
    avatar_1920 = fields.Binary(related="employee_id.avatar_1920", string="Avatar 1920")
    is_rest_day = fields.Boolean(
        string="Is Rest Day",
        help="This will make current day as rest day",
        default=False,
        readonly=False,
    )

    @api.onchange("is_rest_day")
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_shift_id and self.is_rest_day:
            self.check_in_status = "restday"
            self.check_out_status = "restday"
            self.late_time = "00:00:00"
            self.early_time = "00:00:00"
        else:
            if not self.is_rest_day:
                self.action_shift_now()

    def float_time_to_exact_time(self, float_time_):
        # Extract hours
        hours = int(float_time_)
        # Extract minutes and seconds from the fractional part
        fractional_part = float_time_ - hours
        minutes = int(fractional_part * 60)
        seconds = int(round((fractional_part * 60 - minutes) * 60))
        # Format the time string
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get_day_of_week(self, date_time_):
        day = date_time_.strftime("%A")
        return day

    def datetime_to_float_time(self, datetime_):
        # Extract hours, minutes, and seconds from the datetime object
        hours = datetime_.hour
        minutes = datetime_.minute
        seconds = datetime_.second
        # Convert to float where the time is represented as HH.MMSS
        float_time = hours + minutes / 60.0 + seconds / 3600.0
        return float_time

    def action_shift_now(self):
        if not self.employee_shift_id:
            raise UserError("Please select a shift.")

        elif not self.check_in:
            raise UserError("Please select a check in time.")

        elif not self.check_out:
            raise UserError("Please select a check out time.")

        elif self.employee_id and self.check_in and self.check_out and self.employee_shift_id:
            # initializing local variables
            check_in, check_out, early_out, check_in_status, check_out_status, rest_days_ = 0, 0, 0, "", "", []
            # Calculating Early Out
            early_out = self.employee_shift_id.short_leave - self.employee_shift_id.shift_start

            # To avoid multiple check_in and check_out addition with time difference
            check_in = self.datetime_to_float_time(self.check_in + timedelta(hours=5))
            check_out = self.datetime_to_float_time(self.check_out + timedelta(hours=5))
            late_minutes, early_minutes = 0, 0

            # Checking Check-In Status and late minutes
            if check_in <= (self.employee_shift_id.shift_start + self.employee_shift_id.margin):
                check_in_status = "presentontime"
            elif (
                (self.employee_shift_id.shift_start + self.employee_shift_id.margin)
                < check_in
                <= self.employee_shift_id.late_end
            ):
                check_in_status = "late"
                late_minutes = check_in - self.employee_shift_id.shift_start
            elif self.employee_shift_id.late_end < check_in <= self.employee_shift_id.short_leave:
                check_in_status = "shortleave"
            elif check_in > self.employee_shift_id.short_leave:
                check_in_status = "absent"
            else:
                if not check_in:
                    check_in_status = "absent"

            # Checking Check-Out Status
            if check_out >= (self.employee_shift_id.shift_end - self.employee_shift_id.margin):
                check_out_status = "presentontime"
            elif early_out >= (self.employee_shift_id.shift_end - check_out) and check_out <= (
                self.employee_shift_id.shift_end - self.employee_shift_id.margin
            ):
                early_minutes = self.employee_shift_id.shift_end - check_out
                check_out_status = "shortleave"
            elif check_out <= (self.employee_shift_id.shift_end - self.employee_shift_id.margin):
                check_out_status = "absent"
            else:
                if not check_out:
                    check_out_status = "absent"

            # converting float time to exact time
            late_minutes = self.float_time_to_exact_time(late_minutes)
            early_minutes = self.float_time_to_exact_time(early_minutes)

            if self.is_rest_day:
                check_in_status = "restday"
                check_out_status = "restday"
                late_minutes = "00:00:00"
                early_minutes = "00:00:00"
                self.is_rest_day = True

            #  Updating Attendance Data
            self.sudo().write(
                {
                    "check_in_status": check_in_status,
                    "check_out_status": check_out_status,
                    "employee_shift_id": self.employee_shift_id.id,
                    "late_time": late_minutes if late_minutes != "00:00:00" else None,
                    "early_time": early_minutes if early_minutes != "00:00:00" else None,
                }
            )

            message = f"Attendance adjustment completed successfully. {self.employee_id.name} record was updated."
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "title": _("Successful"),
                    "message": _(message),
                    "sticky": True,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
