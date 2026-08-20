# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HrRest_day(models.Model):
    _name = 'hr.rest_day'
    _description = 'HrRest_day'

    name = fields.Char('Name')
