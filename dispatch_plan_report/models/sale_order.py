# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_add_to_dispatch_list(self):
        """Adds the selected Sales Orders to the current user's persistent
        Dispatch List. Safe to call repeatedly - duplicates are skipped.
        Bound to the 'Actions' (gear) menu on sale.order, works from both
        the list view (multi-select, survives pagination) and the form view.
        """
        CartLine = self.env['dispatch.plan.cart.line']
        already_in_list = CartLine.search([
            ('user_id', '=', self.env.uid),
            ('sale_order_id', 'in', self.ids),
        ]).mapped('sale_order_id')

        to_add = self - already_in_list
        for order in to_add:
            CartLine.create({
                'user_id': self.env.uid,
                'sale_order_id': order.id,
            })

        if to_add and already_in_list:
            message = "%d order(s) added, %d were already in your Dispatch List." % (
                len(to_add), len(already_in_list))
        elif to_add:
            message = "%d order(s) added to your Dispatch List." % len(to_add)
        else:
            message = "All selected order(s) were already in your Dispatch List."

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dispatch List',
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }