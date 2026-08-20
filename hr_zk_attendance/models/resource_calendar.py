# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'
    shift_start = fields.Float(string='Shift Start', default=9.0)
    shift_end = fields.Float(string='Shift End', default=18.0)