# -*- coding: utf-8 -*-
import logging
import pytz
from markupsafe import Markup

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Please Install pyzk library.")
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class BiometicMachineData(models.Model):
    _name = "biometic.machine.data"
    _description = "BiometicMachineData"

    name = fields.Char("Name")
    user_machine_id = fields.Many2one("biometric.device.details", "User Machine")
    employee_name = fields.Char("Employee Name")
    uid = fields.Char("UID")
    group_id = fields.Char("Group ID")
    card = fields.Char("Card")
    password = fields.Char("Password")
    privilege = fields.Char("Privilege")
    user_id = fields.Char("User ID")

