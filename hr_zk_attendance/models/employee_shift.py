# -*- coding: utf-8 -*-

from datetime import timedelta
from odoo import models, fields, api


class EmployeeShift(models.Model):
    _name = "employee.shift"
    _description = "Employee Shifts"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    name = fields.Char("Name", required=True, tracking=True)
    resource_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Working Schedule",
        tracking=True,
        help=(
            "The Working Schedule (used by Odoo's payroll, overtime, and "
            "time-off features) that corresponds to this shift. When this "
            "shift is assigned to an employee (including via the bulk "
            "shift-change wizard), this Working Schedule will also be set "
            "on their contract automatically, so payroll/overtime "
            "calculations stay in sync with the shift used for attendance "
            "tracking. Leave blank if this shift has no equivalent "
            "Working Schedule set up yet."
        ),
    )
    shift_type = fields.Selection(
        [
            ("Morning", "Morning"),
            ("Evening", "Evening"),
            ("Night", "Night"),
            ("Gazette Morning", "Gazette Morning"),
            ("Gazette Night", "Gazette Night"),
        ],
        string="Shift Type",
        required=True,
        tracking=True,
    )
    shift_start = fields.Float(
        "Shift Start",
        required=True,
        tracking=True,
        help="Start time of working.\n"
        "A specific value of 24:00 is interpreted as 23:59:59.999999.",
    )
    shift_end = fields.Float(
        "Shift End",
        tracking=True,
        compute="_compute_sum_total",
        store=True,
        help="End time of working.\n"
        "A specific value of 24:00 is interpreted as 23:59:59.999999.",
    )
    shift_duration = fields.Integer(
        "Shift Duration",
        tracking=True,
        default=9,
        help="Duration of working in hours.",
    )
    margin = fields.Float(
        "Margin",
        required=True,
        tracking=True,
        help="Margin time before the shift start.\n"
        "A specific value of 24:00 is interpreted as 23:59:59.999999.",
    )
    present_end = fields.Float(
        "Present End",
        tracking=True,
        help="End time of the present.\n"
        "A specific value of 24:00 is interpreted as 23:59:59.999999.",
        compute="_compute_sum_total",
        store=True,
    )
    late_end = fields.Float(
        "Late End",
        required=True,
        tracking=True,
        help="End time for being considered late.\n"
        "A specific value of 24:00 is interpreted as 23:59:59.999999.",
    )

    short_leave = fields.Float(
        "Short Leave",
        required=True,
        tracking=True,
        help="Duration of short leave in hours.",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("hr", "HR Approval"),
            ("approved", "Approved"),
            ("cancel", "Cancel"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
    )

    def action_hr_approval(self):
        self.state = "hr"

    def action_approved(self):
        self.state = "approved"

    def action_cancel(self):
        self.state = "cancel"

    def action_reject(self):
        self.state = "rejected"

    def action_draft(self):
        self.state = "draft"

    @api.depends("margin", "shift_duration", "shift_start")
    def _compute_sum_total(self):
        for rec in self:
            if rec.shift_start > 0 or rec.margin:
                rec.present_end = rec.shift_start + rec.margin
                rec.late_end = rec.shift_start + 1
                rec.short_leave = rec.shift_start + 2

                # Convert shift_start and shift_duration to timedelta
                shift_start_td = timedelta(hours=rec.shift_start)
                shift_duration_td = timedelta(hours=rec.shift_duration)

                # Calculate shift_end as a timedelta
                shift_end_td = shift_start_td + shift_duration_td

                # Convert shift_end back to hours, ensuring it's within 0-23
                rec.shift_end = shift_end_td.total_seconds() / 3600 % 24