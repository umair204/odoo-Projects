import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"
    
    # This function will show all the attendances of the current logged in user.
    def action_open_all_attendances(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("All Attendances"),
            "res_model": "hr.attendance",
            "views": [[self.env.ref('hr_attendance.hr_attendance_employee_simple_tree_view').id, "tree"]],
            "context": {
                "create": 0,
                "delete": 0,
                "group_by": "check_in"
            },
            "domain": [('employee_id', '=', self.employee_id.id)] 
        }
