# -*- coding: utf-8 -*-
{
    'name': 'Digital Infotech Report',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'summary': 'Custom Header and Footer For Reports',
    'description': """Custom header and footer for Odoo PDF reports, including:
                      Sales Orders, Purchase Orders, Invoices, and Delivery Notes.
                      Supports all related sales documents.""",
    'author': 'Muhammad Umair Aslam',
    'company': 'Muhammad Umair Aslam',
    'maintainer': 'Muhammad Umair Aslam',
    'website': "umairaslam151@gmail.com",
    # any module necessary for this one to work correctly
    'depends': ['base', 'sale_management', 'account', 'stock', 'purchase'],
    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'report/report.xml',
        'report/sale_order_template.xml',
    ],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
