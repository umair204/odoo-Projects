# -*- coding: utf-8 -*-
import datetime

from odoo import models


class DispatchPlanXlsx(models.AbstractModel):
    """XLSX report for the Dispatch Plan, using the 'report_xlsx' module
    (report.report_xlsx.abstract). Bound directly to sale.order, so it shows
    up in the standard Print dropdown for one or more selected Sales Orders.
    """
    _name = 'report.dispatch_plan_report.report_dispatch_plan_xlsx'
    _description = 'Dispatch Plan XLSX Report'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, orders):
        sheet = workbook.add_worksheet('Dispatch Plan')

        header_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#F2F2F2',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })
        title_fmt = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
        })
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy'})
        text_fmt = workbook.add_format({'border': 1})
        num_fmt = workbook.add_format({'border': 1, 'num_format': '0.00', 'align': 'right'})

        headers = [
            '#', 'Customer PO#', 'Promise Date', 'SO #', 'Product', 'Customer Name',
            'Order Qty', 'UoM', 'Dispatch Qty', 'Remaining Qty', 'Current Dispatch',
            'Dispatcher Name/Sign',
        ]
        col_widths = [5, 14, 14, 12, 28, 26, 10, 8, 12, 12, 14, 22]
        for col, width in enumerate(col_widths):
            sheet.set_column(col, col, width)

        date_fmt_center = workbook.add_format({'align': 'center'})

        sheet.merge_range(0, 0, 0, len(headers) - 1, 'Dispatch Plan', title_fmt)
        sheet.merge_range(1, 0, 1, len(headers) - 1, datetime.date.today().strftime('%d/%m/%Y'), date_fmt_center)

        header_row = 3
        for col, label in enumerate(headers):
            sheet.write(header_row, col, label, header_fmt)

        report_model = self.env['report.dispatch_plan_report.report_dispatch_plan_document']
        lines = report_model._build_lines(orders)

        row = header_row + 1
        if not lines:
            sheet.merge_range(row, 0, row, len(headers) - 1,
                               'No order lines found for the selected Sales Orders.', text_fmt)
            row += 1
        else:
            for idx, line in enumerate(lines, start=1):
                sheet.write(row, 0, idx, text_fmt)
                sheet.write(row, 1, line['customer_po'], text_fmt)
                sheet.write(row, 2, str(line['promise_date'] or ''), date_fmt)
                sheet.write(row, 3, line['so_number'], text_fmt)
                sheet.write(row, 4, line['product'], text_fmt)
                sheet.write(row, 5, line['customer'], text_fmt)
                sheet.write_number(row, 6, line['order_qty'], num_fmt)
                sheet.write(row, 7, line['uom'], text_fmt)
                sheet.write_number(row, 8, line['dispatch_qty'], num_fmt)
                sheet.write_number(row, 9, line['remaining_qty'], num_fmt)
                sheet.write(row, 10, line['current_dispatch'], text_fmt)
                sheet.write(row, 11, '', text_fmt)
                row += 1

        row += 1
        sheet.write(row, 0, 'Sales Signatures:')
        sheet.write(row, len(headers) - 3, 'Dispatch Signature:')