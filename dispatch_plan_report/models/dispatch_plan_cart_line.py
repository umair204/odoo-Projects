# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class DispatchPlanCartLine(models.Model):
    """A persistent, per-user 'Dispatch List'.
    Sales Orders get added here (from any list page, any filter) via the
    "Add to Dispatch List" action, so the selection survives pagination,
    filter changes, and navigating away - unlike native list-view checkbox
    selection which resets every time the page/filter changes.
    """
    _name = 'dispatch.plan.cart.line'
    _description = 'Dispatch Plan - Selected Sales Order'
    _order = 'commitment_date, so_number'

    user_id = fields.Many2one(
        'res.users', string='Added By', required=True,
        default=lambda self: self.env.user, index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order', required=True, ondelete='cascade', index=True,
    )
    so_number = fields.Char(related='sale_order_id.name', string='SO #', store=True, readonly=True)
    client_order_ref = fields.Char(related='sale_order_id.client_order_ref', string='Customer PO#', readonly=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', string='Customer', readonly=True)
    commitment_date = fields.Datetime(related='sale_order_id.commitment_date', string='Promise Date', store=True, readonly=True)
    amount_total = fields.Monetary(related='sale_order_id.amount_total', readonly=True)
    currency_id = fields.Many2one(related='sale_order_id.currency_id', readonly=True)
    added_on = fields.Datetime(string='Added On', default=fields.Datetime.now, readonly=True)

    _sql_constraints = [
        ('uniq_user_order', 'unique(user_id, sale_order_id)',
         'This Sales Order is already in your Dispatch List.'),
    ]

    def action_print_pdf(self):
        orders = self.mapped('sale_order_id')
        if not orders:
            raise UserError("Please select at least one line to print.")
        return self.env.ref('dispatch_plan_report.action_report_dispatch_plan').report_action(orders)

    def action_print_xlsx(self):
        orders = self.mapped('sale_order_id')
        if not orders:
            raise UserError("Please select at least one line to print.")
        return self.env.ref('dispatch_plan_report.action_report_dispatch_plan_xlsx').report_action(orders)

    @api.model
    def action_clear_my_list(self):
        """Removes every line belonging to the current user."""
        self.search([('user_id', '=', self.env.uid)]).unlink()
        return True

    @api.model
    def _get_my_cart_lines(self):
        cart_lines = self.search([('user_id', '=', self.env.uid)])
        if not cart_lines:
            raise UserError(
                "Your Dispatch List is empty. Select Sales Order(s) and click "
                "'Add to Dispatch List' first, then use Print again."
            )
        return cart_lines

    @api.model
    def action_print_all_pdf(self):
        """Prints the Dispatch Plan PDF for every order currently in the
        current user's Dispatch List, then clears the list. Bound to the
        'Print' dropdown on sale.order - ignores whatever is selected there,
        it always prints the standing Dispatch List instead."""
        cart_lines = self._get_my_cart_lines()
        orders = cart_lines.mapped('sale_order_id')
        action = self.env.ref('dispatch_plan_report.action_report_dispatch_plan').report_action(orders)
        cart_lines.unlink()
        return action

    @api.model
    def action_print_all_xlsx(self):
        """Same as action_print_all_pdf, but for the XLSX report."""
        cart_lines = self._get_my_cart_lines()
        orders = cart_lines.mapped('sale_order_id')
        action = self.env.ref('dispatch_plan_report.action_report_dispatch_plan_xlsx').report_action(orders)
        cart_lines.unlink()
        return action