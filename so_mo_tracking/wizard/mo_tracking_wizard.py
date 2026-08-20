# -*- coding: utf-8 -*-
import base64
import io
import re
from datetime import datetime, time as dtime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

STATE_LABELS = {
    'draft': 'Draft',
    'confirmed': 'Confirmed',
    'planned': 'Planned',
    'progress': 'In Progress',
    'to_close': 'To Close',
    'done': 'Done',
    'cancel': 'Cancelled',
}

# Safety cap in case of a data loop (origin pointing back on itself).
MAX_CHAIN_DEPTH = 25


class SaleOrderMoTrackingWizard(models.TransientModel):
    _name = 'sale.order.mo.tracking.wizard'
    _description = 'Sale Order Manufacturing Tracking'

    # --- Option 1: look up one specific SO ---
    so_id = fields.Many2one('sale.order', string='Sale Order')
    so_name = fields.Char(
        string='Or type SO number',
        help="Look up a single SO directly. Leave both of these empty and "
             "use the Delivery Date range below to see all SOs in a period "
             "instead.",
    )

    # --- Option 2: filter by Delivery Date range (sale.order.commitment_date) ---
    date_from = fields.Date(string='Delivery Date From')
    date_to = fields.Date(string='Delivery Date To')

    line_ids = fields.One2many(
        'sale.order.mo.tracking.wizard.line', 'wizard_id',
        string='Manufacturing Stages',
    )
    not_found = fields.Boolean(default=False)
    searched = fields.Boolean(default=False)

    @api.onchange('so_id')
    def _onchange_so_id(self):
        if self.so_id:
            self.so_name = self.so_id.name

    def action_search(self):
        self.ensure_one()
        SaleOrder = self.env['sale.order']

        self.line_ids.unlink()
        self.searched = True
        self.not_found = False

        # Priority 1: a specific SO (selected via so_id, or typed in so_name)
        single_order = self.so_id
        if not single_order and self.so_name:
            typed = self.so_name.strip()
            single_order = SaleOrder.search([('name', '=', typed)], limit=1)
            if not single_order:
                single_order = SaleOrder.search([('name', 'like', typed)], limit=1)

        if single_order:
            orders = single_order
            self.so_id = single_order.id
            self.so_name = single_order.name
        else:
            # Priority 2: Delivery Date range
            self.so_id = False
            domain = []
            if self.date_from:
                domain.append(('commitment_date', '>=', datetime.combine(self.date_from, dtime.min)))
            if self.date_to:
                domain.append(('commitment_date', '<=', datetime.combine(self.date_to, dtime.max)))

            if not domain:
                # Nothing to search on at all.
                self.not_found = True
                return self._reopen()

            orders = SaleOrder.search(domain, order='commitment_date asc')

        if not orders:
            self.not_found = True
            return self._reopen()

        lines_vals = []
        seq = 10
        for so in orders:
            final_mos = self.env['mrp.production'].search([('origin', '=', so.name)])

            # Backorder-split MOs (e.g. "MWH/MO/59932-001", "-002") keep the
            # same origin as the SO, but any earlier-stage MO that fed the
            # ORIGINAL (pre-split) production still points at the un-suffixed
            # base name. Group siblings by that base name so they share one
            # upstream chain instead of each independently searching for a
            # child under their own suffixed name (which would never match).
            groups = {}
            group_order = []
            for fm in final_mos:
                key = self._base_name(fm.name)
                if key not in groups:
                    groups[key] = []
                    group_order.append(key)
                groups[key].append(fm)

            so_rows = []
            for key in group_order:
                members = groups[key]
                representative = members[0]
                member_names = [m.name for m in members]
                earlier_stages = self._walk_earlier_stages(member_names)
                for mo in earlier_stages:
                    so_rows.append((representative, mo))
                for mo in members:
                    # Each backorder/final sibling gets its own row (it may
                    # have a different quantity/state from the others).
                    so_rows.append((mo, mo))

            if not so_rows:
                continue  # this SO has no manufacturing chain at all - skip it

            # Leftover per stage: how much of what a stage produced hasn't
            # been drawn into a later stage. Computed by matching each
            # stage's product against every OTHER stage's raw-material
            # consumption lines within this same SO's chain - not just the
            # immediate next row - since a stage's output can, in principle,
            # be consumed by any later MO in the tree, not only its direct
            # neighbour in the flattened list.
            all_mos_this_so = [mo for _, mo in so_rows]
            leftover_map = {}
            for mo in all_mos_this_so:
                consumed = 0.0
                for other in all_mos_this_so:
                    if other.id == mo.id:
                        continue
                    for line in other.move_raw_ids:
                        if line.product_id.id == mo.product_id.id:
                            consumed += line.quantity
                leftover_map[mo.id] = mo.qty_produced - consumed

            done_count = sum(1 for _, mo in so_rows if mo.state == 'done')
            total_count = len(so_rows)
            order_date = so.date_order.date() if so.date_order else 'N/A'
            delivery = so.commitment_date.date() if so.commitment_date else 'N/A'
            dispatch_date = self._get_dispatch_date(so)

            # --- Section header row (bold, its own visual block) ---
            lines_vals.append((0, 0, {
                'sequence': seq,
                'so_id': so.id,
                'so_name': so.name,
                'is_header': True,
                'final_product': (
                    'SO %s   |   Order Date: %s   |   Delivery: %s   |   '
                    'Dispatch Date: %s   |   %d / %d stages done'
                ) % (
                    so.name, order_date, delivery, dispatch_date,
                    done_count, total_count,
                ),
            }))
            seq += 10

            # --- Detail rows for this SO ---
            for final_mo, mo in so_rows:
                stage = self._get_stage(mo.product_id)
                if stage == 'FINAL':
                    leftover_display = ''  # not consumed by anything in this chain
                else:
                    leftover_display = '%.2f' % leftover_map.get(mo.id, 0.0)
                lines_vals.append((0, 0, {
                    'sequence': seq,
                    'so_id': so.id,
                    'so_name': so.name,
                    'final_product': final_mo.product_id.display_name,
                    'stage': stage,
                    'mo_id': mo.id,
                    'mo_name': mo.name,
                    'product_id': mo.product_id.id,
                    'state': mo.state,
                    'state_label': STATE_LABELS.get(mo.state, (mo.state or '').title()),
                    'qty_producing': '%.2f' % mo.qty_producing,
                    'product_qty': '%.2f' % mo.product_qty,
                    'leftover': leftover_display,
                    'entry_date': self._get_entry_date(mo),
                    'end_date': mo.date_finished if 'date_finished' in mo._fields else False,
                    'origin': mo.origin,
                }))
                seq += 10

        self.line_ids = lines_vals
        if not lines_vals:
            # SO(s) matched but none have any linked Manufacturing Orders.
            self.not_found = True
        return self._reopen()

    @staticmethod
    def _get_dispatch_date(so):
        """Dispatch Date = the Effective Date (date_done) of the SO's
        outgoing delivery picking - i.e. when it was actually shipped, not
        when it was scheduled. If there are multiple deliveries (e.g. partial
        shipments), the most recently completed one is used."""
        pickings = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing' and p.date_done
        )
        if not pickings:
            return 'N/A'
        latest = pickings.sorted('date_done', reverse=True)[0]
        return latest.date_done.date()

    def _walk_earlier_stages(self, start_names):
        """Given one or more MO names (e.g. all backorder siblings sharing a
        base name), find every earlier-stage MO that fed into ANY of them,
        across every branch, ordered earliest-first. Does NOT include MOs
        named in `start_names` themselves.

        This walks level by level rather than following a single linear
        chain, because a stage can itself have been backorder-split into
        multiple sibling MOs (e.g. an SLT stage split into "-001" and
        "-002"), and a simple single-child search would silently drop every
        sibling but one.

        Falls back to the backorder/split base name (e.g.
        "MWH/MO/59932-001" -> "MWH/MO/59932") whenever a direct match isn't
        found, since Odoo keeps the earlier-stage MO's `origin` pointed at
        whatever name the requesting MO had BEFORE any backorder split.
        """
        if isinstance(start_names, str):
            start_names = [start_names]

        Production = self.env['mrp.production']
        levels = []
        seen_names = set(start_names)
        current_names = list(start_names)

        for _i in range(MAX_CHAIN_DEPTH):
            next_level = Production.search([('origin', 'in', current_names)])
            next_level = next_level.filtered(lambda p: p.name not in seen_names)
            if not next_level:
                base_names = list({self._base_name(n) for n in current_names})
                base_names = [b for b in base_names if b not in current_names]
                if base_names:
                    next_level = Production.search([('origin', 'in', base_names)])
                    next_level = next_level.filtered(lambda p: p.name not in seen_names)
            if not next_level:
                break
            levels.append(next_level)
            seen_names.update(next_level.mapped('name'))
            current_names = next_level.mapped('name')

        chain = []
        for lvl in reversed(levels):  # earliest stage first
            chain.extend(lvl)
        return chain

    @staticmethod
    def _base_name(name):
        """Strip a trailing Odoo backorder/split suffix like "-001" so
        "MWH/MO/59932-001" becomes "MWH/MO/59932". Returns the name
        unchanged if there's no such suffix."""
        return re.sub(r'-\d+$', '', name or '')

    @staticmethod
    def _get_entry_date(mo):
        """Entry Date is a Studio-added custom field (x_studio_entry_date).
        Defensive in case it's ever renamed or missing on a given instance."""
        if 'x_studio_entry_date' in mo._fields:
            return mo.x_studio_entry_date
        return False

    @staticmethod
    def _get_stage(product):
        """PRT/RWD/LMT/SLT etc. are stored as a suffix on default_code,
        e.g. '10298|SLT'. The final assembly has no suffix."""
        code = product.default_code or ''
        if '|' in code:
            return code.split('|')[-1].strip().upper()
        return 'FINAL'

    def get_grouped_lines(self):
        """Used by the print report: group the flat line_ids by SO while
        preserving the order they were generated in (production order).
        Returns (header_text, detail_lines) pairs - header_text is the full
        descriptive line (SO / Order Date / Delivery / Dispatch / progress)
        from the on-screen section header row, so PDF/XLSX show the same
        detail as the screen, not just the bare SO name."""
        self.ensure_one()
        headers = {}
        groups = {}
        order = []
        for line in self.line_ids:
            key = line.so_name or 'N/A'
            if key not in groups:
                groups[key] = []
                order.append(key)
            if line.is_header:
                headers[key] = line.final_product
                continue
            groups[key].append(line)
        return [(headers.get(key, 'SO: %s' % key), groups[key]) for key in order]

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Manufacturing Order Tracking',
            'res_model': 'sale.order.mo.tracking.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('so_mo_tracking.action_report_so_mo_tracking').report_action(self)

    def action_print_xlsx(self):
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(_(
                "The 'xlsxwriter' Python library is not available on this "
                "server. Please ask your system administrator to install it "
                "(pip install xlsxwriter)."
            ))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('MO Tracking')

        section_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1,
        })
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'border': 1,
        })
        done_fmt = workbook.add_format({'bg_color': '#C6E0B4', 'border': 1})
        pending_fmt = workbook.add_format({'bg_color': '#FFF2CC', 'border': 1})
        muted_fmt = workbook.add_format({'bg_color': '#F2F2F2', 'border': 1})
        normal_fmt = workbook.add_format({'border': 1})
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd hh:mm'})
        date_only_fmt = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})

        columns = ['Stage', 'MO', 'Product', 'Status', 'Qty Producing',
                   'Qty To Produce', 'Leftover', 'Entry Date', 'End Date']
        col_widths = [10, 18, 42, 14, 14, 16, 12, 18, 18]
        for idx, width in enumerate(col_widths):
            sheet.set_column(idx, idx, width)

        row = 0
        groups = self.get_grouped_lines()
        if not groups:
            sheet.write(0, 0, _('No data found.'))
        for header_text, lines in groups:
            sheet.merge_range(
                row, 0, row, len(columns) - 1,
                header_text or 'N/A', section_fmt,
            )
            row += 1
            for c, label in enumerate(columns):
                sheet.write(row, c, label, header_fmt)
            row += 1
            for line in lines:
                if line.state == 'done':
                    fmt = done_fmt
                elif line.state in ('draft', 'cancel'):
                    fmt = muted_fmt
                else:
                    fmt = pending_fmt
                sheet.write(row, 0, line.stage or '', fmt)
                sheet.write(row, 1, line.mo_name or '', fmt)
                sheet.write(row, 2, line.product_id.display_name or '', fmt)
                sheet.write(row, 3, line.state_label or '', fmt)
                sheet.write(row, 4, line.qty_producing or '', fmt)
                sheet.write(row, 5, line.product_qty or '', fmt)
                sheet.write(row, 6, line.leftover or '', fmt)
                if line.entry_date:
                    sheet.write_datetime(row, 7, datetime.combine(line.entry_date, dtime.min), date_only_fmt)
                else:
                    sheet.write(row, 7, '', fmt)
                if line.end_date:
                    sheet.write_datetime(row, 8, line.end_date, date_fmt)
                else:
                    sheet.write(row, 8, '', fmt)
                row += 1
            row += 1  # blank spacer row between SOs

        workbook.close()
        output.seek(0)
        file_data = output.read()

        attachment = self.env['ir.attachment'].create({
            'name': 'SO_Manufacturing_Tracking.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(file_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


class SaleOrderMoTrackingWizardLine(models.TransientModel):
    _name = 'sale.order.mo.tracking.wizard.line'
    _description = 'Sale Order Manufacturing Tracking Line'
    _order = 'so_name asc, sequence asc'

    wizard_id = fields.Many2one(
        'sale.order.mo.tracking.wizard', ondelete='cascade'
    )
    sequence = fields.Integer(default=10)
    so_id = fields.Many2one('sale.order', string='Sale Order')
    so_name = fields.Char(string='SO Number')
    is_header = fields.Boolean(
        default=False,
        help="True for the bold section-title row shown before each SO's block.",
    )
    final_product = fields.Char(string='Final Product')
    stage = fields.Char(string='Stage')
    mo_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    mo_name = fields.Char(string='MO Reference')
    product_id = fields.Many2one('product.product', string='Product')
    state = fields.Char(string='Raw State')
    state_label = fields.Char(string='Status')
    qty_producing = fields.Char(string='Qty Producing')
    product_qty = fields.Char(string='Qty To Produce')
    leftover = fields.Char(
        string='Leftover',
        help="What this stage produced minus what a later stage has "
             "actually consumed of it. Positive = surplus not yet drawn "
             "on; negative = the later stage pulled more than this batch "
             "produced (drew from other/older stock too). Blank for the "
             "Final stage, since nothing later in this chain consumes it.",
    )
    entry_date = fields.Date(string='Entry Date')
    end_date = fields.Datetime(string='End Date')
    origin = fields.Char(string='Origin')