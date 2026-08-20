# Dispatch Plan Report (`dispatch_plan_report`)

Odoo 17 module that adds a persistent, per-user **Dispatch List** on Sales Orders, and prints it as a **Dispatch Plan Report** in PDF and Excel (XLSX).

## Overview

Warehouse/dispatch teams often need to build up a print-ready dispatch list by picking Sales Orders across multiple pages, filters, and sessions — something the native list-view checkbox selection doesn't support, since it resets on every page or filter change.

This module solves that with a **standing, per-user cart** (`dispatch.plan.cart.line`): orders added to it stay there until printed, regardless of navigation, and the module always prints the full accumulated list rather than whatever happens to be ticked at print time.

## Key Features

- **"Add to Dispatch List" action** — available in the Quotations/Sales Orders list (multi-select, works across pages and filters) and on a single order's form view (via the Actions/gear menu).
- **Persistent per-user list** — selections accumulate across sessions until explicitly printed or cleared; duplicate adds are safely skipped.
- **Print from the standing list** — from the Print dropdown on Sales Orders, "Dispatch Plan Report" (PDF) and "Dispatch Plan Report (XLSX)" print everything currently in the user's Dispatch List (not just what's ticked), then automatically empty the list afterward.
- **Full-page fallback view** — Sales > Reporting > Dispatch List, to review or remove individual entries, or print directly from there.
- **Report content** — per order line: Customer PO#, Promise Date, SO #, Product, Customer, Order Qty, Dispatch Qty, Remaining Qty, plus blank Current Dispatch and Dispatcher Name/Sign columns for manual fill-in.

## Module Structure

```
dispatch_plan_report/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── dispatch_plan_cart_line.py   # the persistent per-user Dispatch List + print actions
│   └── sale_order.py                # "Add to Dispatch List" action on sale.order
├── report/
│   ├── __init__.py
│   ├── dispatch_plan_report.py
│   ├── dispatch_plan_report.xml     # PDF report definition
│   └── dispatch_plan_xlsx.py        # XLSX report generation
├── views/
│   ├── dispatch_plan_cart_views.xml # Dispatch List fallback view (Sales > Reporting)
│   ├── sale_order_action.xml
│   └── sale_order_tree_button.xml
└── security/
    ├── dispatch_plan_security.xml
    └── ir.model.access.csv
```

## Dependencies

- Odoo apps: `sale_management`, `report_xlsx`

## Installation

1. Copy the `dispatch_plan_report` folder into your Odoo `custom_addons` directory.
2. Update the Apps list (Settings → Apps → Update Apps List).
3. Search for **Dispatch Plan Report** and click Install.

## Usage

1. In the Quotations or Sales Orders list, tick the Sales Order(s) you want and click **Add to Dispatch List** (next to Print / Actions). Repeat across as many pages/filters as needed — every tick adds to your standing list.
2. When ready, tick any row (just to enable the Print button) and open **Print → Dispatch Plan Report** or **Dispatch Plan Report (XLSX)**. This prints everything currently in your Dispatch List, then clears it automatically.
3. Alternatively, go to **Sales → Reporting → Dispatch List** to review, remove individual entries, or print directly from that screen.
4. "Add to Dispatch List" is also available under **Actions** (gear menu) on a single order's form view.

## Notes

- The Dispatch List is scoped per user (`user_id`) — each user has their own independent standing list.
- A Sales Order can only appear once per user in the list (`unique(user_id, sale_order_id)` constraint); re-adding an already-listed order is a no-op.
- Printing via the "Print" dropdown (`action_print_all_pdf` / `action_print_all_xlsx`) always uses the full standing list and clears it afterward. Printing from the fallback Dispatch List view (`action_print_pdf` / `action_print_xlsx`) prints only the rows you've selected there and does not clear the list.

## License

LGPL-3

## Author

Umair Abbas
