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


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _default_rest_days(self):
        return self.env["hr.rest_day"].search([("name", "in", ["Saturday", "Sunday"])]).ids

    employee_shift_id = fields.Many2one(
        related="contract_id.employee_shift_id", string="Employee Shift", store=True, groups="hr.group_hr_user"
    )
    device_id_num = fields.Char("Device ID Number", tracking=True, groups="hr.group_hr_user")
    rest_days_ids = fields.Many2many(
        "hr.rest_day",
        string="Rest Days",
        groups="hr.group_hr_user",
        default=_default_rest_days,
    )
    is_zk_configured = fields.Boolean(
        string="Is ZK Configured", default=False, groups="hr.group_hr_user", tracking=True
    )
    
    location_id = fields.Many2one(
        "stock.location", string="Stock Location",tracking=True, groups="hr.group_hr_user"
    )
    
    # def create_employee_stock_location(self):
    #     for employee in self:
    #         if not employee.location_id:
    #             location_id = self.env["stock.location"].search(
    #                 [
    #                     ("name", "=", "Employee"),
    #                     ("unique_id", "not in", [_("New"), "N/A"]),
    #                     ("company_id", "=", self.env.company.id),
    #                 ],
    #                 limit=1,
    #             )
    #             location_vals = {
    #                 "name": f"{employee.unique_id}-{employee.name}",
    #                 "usage": "internal",
    #                 "location_id": location_id.id,
    #                 "station_id": employee.station_id.id,
    #                 "street": employee.work_contact_id.street,
    #                 "company_id": self.env.company.id,
    #             }
    #             location_id = (
    #                 self.env["stock.location"].sudo().create(location_vals)
    #             )
    #             if location_id:
    #                 employee.work_contact_id.property_stock_customer = location_id
    #                 employee.location_id = location_id
    #
    #             _logger.info("Location Created: %s", location_id)

    
    
    

    # @api.model_create_multi
    # def create(self, vals_list):
    #     res = super().create(vals_list)
    #     for rec in res:
    #         if not rec.device_id_num:
    #             if rec.work_contact_id.unique_id:
    #                 unique_id = str(rec.work_contact_id.unique_id)
    #                 unique_id = unique_id[4::]
    #                 rec.barcode = unique_id
    #                 rec.device_id_num = unique_id
    #             else:
    #                 rec.barcode = "NILL"
    #                 rec.device_id_num = "NILL"
    #     return res
    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            if not rec.device_id_num:
                rec.barcode = "NILL"
                rec.device_id_num = "NILL"
        return res

    def write(self, vals):
        res =  super(HrEmployee,self).write(vals)
        selected_day = []
        removed_day = []

        if vals.get('rest_days_ids'):
            for record in vals.get('rest_days_ids'):
                if record[0] == 4:
                    selected_day.append(self.env['hr.rest_day'].sudo().browse(record[1]).name)
                if record[0] == 3:
                    removed_day.append(self.env['hr.rest_day'].sudo().browse(record[1]).name)
            if selected_day:
                join_selected_days = ", ".join(selected_day)
                body = _('%s selected as Rest Days', join_selected_days)
                self.sudo().message_post(body=body)
            if removed_day:
                join_removed_days = ", ".join(removed_day)
                body = _('%s removed from Rest Days', join_removed_days)
                self.sudo().message_post(body=body)
        return res

    def create_new_employee(self):
        """Function to create new employee"""
        res = self.env["biometric.device.details"].search([])
        for info in res:
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
                conn = info.device_connect(zk)
                # print(conn)
                if conn:
                    conn.disable_device()  # Device cannot be used during this time.
                    users = conn.get_users()
                    _logger.info("Machine: {} {}".format(info.name, len(users)))
                    user_exist = False
                    for rec in users:
                        if self.device_id_num and rec.user_id == self.device_id_num:
                            user_exist = True
                            self.is_zk_configured = True
                            _logger.error("User already exists in the device.")
                    if self.device_id_num and self.barcode and not user_exist:
                        res = conn.set_user(
                            uid=int(self.device_id_num),
                            name=str(self.name),
                            privilege=const.USER_DEFAULT,
                            password="ADMIN@1122",
                            group_id="",
                            user_id=str(self.device_id_num),
                            card=int(self.device_id_num),
                        )
                        self.is_zk_configured = True
                        self.message_post(
                            body=Markup(f"<div><b>{_('ZK Machine user created id:')} {self.device_id_num}</b></div>")
                        )
                        _logger.info("User created in the device: %s %s", res, self.device_id_num)
                    else:
                        _logger.error("user not created in machine")
                    conn.enable_device()
                    conn.disconnect()
            except Exception as e:
                _logger.error("Process terminated: {}".format(e))
