{
    'name': 'Dispatch Plan Report',
    'version': '17.0.4.0.0',
    'category': 'Sales/Sales',
    'summary': 'Dispatch List + Dispatch Plan report (PDF & XLSX) for Sales Orders',
    'description': """
Dispatch Plan Report
=====================
1. In the Quotations or Sales Orders list, tick the Sales Order(s) you
   want (works across pages/filters - every tick adds to your standing
   list). Click "Add to Dispatch List" (next to Print / Actions).
2. Repeat on as many pages/filters as you like - it all accumulates in
   your personal Dispatch List on the backend, no separate screen needed.
3. When ready, tick any row (just to enable the Print button) and open
   Print -> "Dispatch Plan Report" or "Dispatch Plan Report (XLSX)".
   This prints EVERYTHING currently in your Dispatch List (not just what's
   ticked at that moment), then automatically empties the list.

A full-page fallback is also available at Sales > Reporting > Dispatch
List, to review/remove individual entries or print from there instead.
"Add to Dispatch List" is also available under Actions (gear menu) on a
single order's form view.

The printed Dispatch Plan lists, per order line: Customer PO#, Promise
Date, SO #, Product, Customer, Order Qty, Dispatch Qty, Remaining Qty,
a blank Current Dispatch column, and a blank Dispatcher Name/Sign column.
""",
    'author': 'Umair Abbas',
    'depends': ['sale_management', 'report_xlsx'],
    'data': [
        'security/ir.model.access.csv',
        'security/dispatch_plan_security.xml',
        'report/dispatch_plan_report.xml',
        'views/sale_order_action.xml',
        'views/sale_order_tree_button.xml',
        'views/dispatch_plan_cart_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}