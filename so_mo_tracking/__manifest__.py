{
    'name': 'Sale Order Manufacturing Tracking',
    'version': '17.0.1.1.0',
    'summary': 'Track the full multi-stage manufacturing chain (PRT/RWD/LMT/SLT ...) linked to a Sale Order',
    'description': """
Sale Order Manufacturing Tracking

The chain is discovered dynamically by walking the `origin` field on
mrp.production records, so it works regardless of how many stages a given
product has.
""",
    'category': 'Manufacturing',
    'author': 'Umair Abbas',
    'depends': ['sale', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'report/so_mo_tracking_report.xml',
        'report/so_mo_tracking_report_templates.xml',
        'views/mo_tracking_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}