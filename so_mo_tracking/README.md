# Sale Order Manufacturing Tracking (`so_mo_tracking`)

Odoo 17 module that traces the **full multi-stage manufacturing chain** (e.g. PRT / RWD / LMT / SLT / FINAL) linked to a Sale Order, and reports it on-screen, as a PDF, or as an Excel export.

## Overview

Many manufacturing setups don't produce a final product in a single Manufacturing Order (MO) — raw material moves through several intermediate MOs (cutting, forming, finishing, etc.) before the final assembly is produced. This module walks that chain automatically by following the `origin` field on `mrp.production` records, so it works no matter how many stages a given product has.

## Key Features

- **Automatic chain discovery** — starting from a Sale Order, the module walks backward through linked MOs via the `origin` field to reconstruct every production stage feeding the final product.
- **Backorder-aware grouping** — MOs split into backorders (e.g. `MWH/MO/59932-001`, `-002`) are grouped by their base reference so they share one upstream chain instead of being tracked separately.
- **Leftover / consumption tracking** — for each stage, calculates how much of what it produced has actually been drawn into later stages (`Leftover` column), so surplus or over-consumption is visible at a glance.
- **Search wizard** with two lookup modes:
  - By a specific Sale Order (pick from a list or type the SO number).
  - By a Delivery Date range, to review all SOs due in a period at once.
- **On-screen tracking view** — grouped by SO, with a summary header (Order Date, Delivery Date, Dispatch Date, stages completed).
- **PDF report** via a QWeb template.
- **Excel (XLSX) export** with color-coded stage status (done / pending / cancelled) — requires the `xlsxwriter` Python library on the server.
- **Sale Order integration** — adds a "Linked MOs" smart button and Product/Unit Price fields directly on the Sale Order form/list.

## Module Structure

```
so_mo_tracking/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── sale_order.py            # sale.order extensions (MO count, list price/product, wizard launcher)
├── wizard/
│   ├── __init__.py
│   └── mo_tracking_wizard.py    # core chain-walking, leftover calc, PDF/XLSX generation
├── report/
│   ├── so_mo_tracking_report.xml
│   └── so_mo_tracking_report_templates.xml
├── views/
│   ├── mo_tracking_wizard_views.xml
│   └── sale_order_views.xml
└── security/
    └── ir.model.access.csv
```

## Dependencies

- Odoo apps: `sale`, `mrp`
- Python library: `xlsxwriter` (only required for the Excel export — install with `pip install xlsxwriter` if not already available on the server)

## Installation

1. Copy the `so_mo_tracking` folder into your Odoo `custom_addons` directory.
2. Update the Apps list (Settings → Apps → Update Apps List).
3. Search for **Sale Order Manufacturing Tracking** and click Install.

## Usage

1. Open a Sale Order and click the **Linked MOs** smart button, **or**
2. Open the tracking wizard directly and search either by SO number or by a Delivery Date range.
3. Review the grouped stage breakdown on screen.
4. Use **Print Report** for a PDF, or **Export to Excel** for an XLSX file.

## Notes

- The manufacturing "stage" label (PRT/RWD/LMT/SLT/etc.) is read from a suffix on the product's internal reference (`default_code`), formatted as `CODE|STAGE` (e.g. `10298|SLT`). A product with no such suffix is treated as `FINAL`.
- `Entry Date` reads from an optional Studio-added field (`x_studio_entry_date`) if present on `mrp.production`; it is skipped safely if that field doesn't exist on a given instance.
- Chain-walking has a safety cap (25 levels) to guard against circular `origin` references in the data.

## License

LGPL-3

## Author

Umair Abbas
