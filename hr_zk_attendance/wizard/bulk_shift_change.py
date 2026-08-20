# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class BulkShiftChange(models.TransientModel):
    """Quickly reassign the current/going-forward Employee Shift for one or
    many employees at once, without needing to open each employee's full
    form individually. Useful for mid-month shift changes (e.g. moving
    someone from Morning to Night shift starting today) or for reassigning
    a whole team at once.

    Note: the actual shift is stored on the employee's Contract
    (hr.contract.employee_shift_id) — hr.employee.employee_shift_id is
    just a read-through mirror of that. Employees with no active contract
    have nowhere to store a shift and are skipped, with a clear message
    explaining why.
    """

    _name = "bulk.shift.change"
    _description = "Bulk Change Employee Shift"

    employee_ids = fields.Many2many(
        "hr.employee",
        string="Employees",
        required=True,
        help="Select one or more employees whose shift should be changed.",
    )
    new_shift_id = fields.Many2one(
        "employee.shift",
        string="New Shift",
        required=True,
        help="This shift will apply to all future attendance processing for the selected employees, starting immediately.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # If launched from the Employees list view with some employees
        # selected, pre-fill them automatically.
        if self.env.context.get("active_model") == "hr.employee" and self.env.context.get("active_ids"):
            res["employee_ids"] = [(6, 0, self.env.context["active_ids"])]
        return res

    def action_apply(self):
        self.ensure_one()
        no_contract = self.employee_ids.filtered(lambda emp: not emp.contract_id)
        with_contract = self.employee_ids - no_contract

        if with_contract:
            vals = {"employee_shift_id": self.new_shift_id.id}
            if self.new_shift_id.resource_calendar_id:
                vals["resource_calendar_id"] = self.new_shift_id.resource_calendar_id.id
            with_contract.mapped("contract_id").write(vals)

        if with_contract:
            message = _(
                "Shift changed to '%s' for %d employee(s): %s"
            ) % (
                self.new_shift_id.name,
                len(with_contract),
                ", ".join(with_contract.mapped("name")),
            )
            if not self.new_shift_id.resource_calendar_id:
                message += "\n" + _(
                    "Note: this shift has no Working Schedule linked to "
                    "it, so the employees' Working Schedule (used for "
                    "payroll/overtime) was NOT changed — only the "
                    "Employee Shift used for attendance tracking was "
                    "updated. Set a Working Schedule on this shift (open "
                    "the shift record) to keep both in sync automatically "
                    "next time."
                )
        else:
            message = _("No employees were updated.")

        if no_contract:
            message += "\n" + _(
                "Skipped %d employee(s) with no active contract (a shift "
                "can only be set on an employee with a contract): %s"
            ) % (len(no_contract), ", ".join(no_contract.mapped("name")))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if with_contract else "warning",
                "title": _("Shift Change"),
                "message": message,
                "sticky": bool(no_contract),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }