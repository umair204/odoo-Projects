# -*- coding: utf-8 -*-
from odoo import fields, models


class DispatchPlanReport(models.AbstractModel):
    """QWeb PDF report parser for the Dispatch Plan document.
    Bound directly to sale.order via binding_model_id, so it shows up in the
    standard Print dropdown for one or more selected Sales Orders.
    """
    _name = 'report.dispatch_plan_report.report_dispatch_plan_document'
    _description = 'Dispatch Plan PDF Report'

    def _get_report_values(self, docids, data=None):
        orders = self.env['sale.order'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'sale.order',
            'docs': orders,
            'lines': self._build_lines(orders),
        }

    def _build_lines(self, orders):
        """Builds one row per (non-section/note) order line across all given orders.
        Shared by both the PDF and XLSX reports.

        'current_dispatch' is intentionally left blank here - filled in by hand
        on the printed sheet, not fetched from the system.
        """
        lines = []
        sorted_orders = orders.sorted(key=lambda o: (o.commitment_date or fields.Datetime.now(), o.name))
        for order in sorted_orders:
            order_lines = order.order_line.filtered(lambda l: not l.display_type)
            for line in order_lines:
                dispatch_qty = line.qty_delivered
                remaining_qty = line.product_uom_qty - dispatch_qty
                lines.append({
                    'customer_po': order.client_order_ref or '',
                    'promise_date': order.commitment_date,
                    'so_number': order.name,
                    'product': line.product_id.display_name or '',
                    'customer': order.partner_id.display_name or '',
                    'order_qty': round(line.product_uom_qty, 2),
                    'uom': line.product_uom.name or '',
                    'dispatch_qty': round(dispatch_qty, 2),
                    'remaining_qty': round(remaining_qty, 2),
                    'current_dispatch': '',  # filled manually on paper
                })
        return lines