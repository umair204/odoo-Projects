# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HrContract(models.Model):
    _inherit = "hr.contract"
    employee_shift_id = fields.Many2one(
        "employee.shift", string="Employee Shift", required=True
    )
    shift_start = fields.Float(
        related="employee_shift_id.shift_start", string="Shift Start", readonly=True
    )
    shift_end = fields.Float(
        related="employee_shift_id.shift_end", string="Shift End", readonly=True
    )
