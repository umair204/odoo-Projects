# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mo_tracking_count = fields.Integer(
        string='Linked MOs',
        compute='_compute_mo_tracking_count',
    )

    list_product_id = fields.Many2one(
        'product.product',
        string='Product',
        compute='_compute_list_product_info',
        store=True,
    )
    list_unit_price = fields.Float(
        string='Unit Price',
        compute='_compute_list_product_info',
        store=True,
        digits='Product Price',
    )

    @api.depends('order_line.product_id', 'order_line.price_unit')
    def _compute_list_product_info(self):
        for order in self:
            line = order.order_line[:1]
            order.list_product_id = line.product_id
            order.list_unit_price = line.price_unit

    def _compute_mo_tracking_count(self):
        Production = self.env['mrp.production']
        for order in self:
            order.mo_tracking_count = Production.search_count(
                [('origin', '=', order.name)]
            )

    def action_view_mo_tracking(self):
        """Open the tracking wizard pre-filled and pre-searched for this SO."""
        self.ensure_one()
        wizard = self.env['sale.order.mo.tracking.wizard'].create({
            'so_id': self.id,
        })
        wizard.action_search()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Manufacturing Order Tracking - %s' % self.name,
            'res_model': 'sale.order.mo.tracking.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
