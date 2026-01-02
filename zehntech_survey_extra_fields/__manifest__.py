{
    "name": "Survey Extra Fields",
    "summary": "Enhance Odoo Survey App with 14 new question field types like Color Pickers, Digital Signatures, File Uploads, and Email validation. This module also includes automated survey scheduling via cron jobs, allowing hands-free distribution to specific contacts. Improve data quality, accuracy, and efficiency for all your Odoo survey needs and data collection processes. Odoo Survey Fields | Survey Extra Fields | Custom Survey Fields | Digital Signature Survey | Color Picker Survey | File Upload Survey | Survey Automation Odoo | Automated Survey Scheduling | Survey Field Validation | Advanced Survey Questions | Survey Cron Jobs | Odoo Survey Enhancement | Survey Data Collection | Custom Question Types | Survey Module Addon",
    "description": """
        Survey Extra Fields module expands the standard Odoo Survey app, adding 14 specialized field types (e.g., Time, Range, Password, URL) for richer data. Features include mandatory field settings, strict input validation, and a powerful automated scheduling option. Use Odoo's cron jobs to automatically send surveys on set dates to targeted contacts, ensuring timely distribution and efficient status tracking. This is essential for advanced data capture and streamlined workflow.
    """,
    "author": "Zehntech Technologies Inc.",
    "company": "Zehntech Technologies Inc.",
    "maintainer": "Zehntech Technologies Inc.",
    "contributor": "Zehntech Technologies Inc.",
    "website": "https://www.zehntech.com/",
    "support": "odoo-support@zehntech.com",
    "live_test_url": "https://zehntechodoo.com/app_name=zehntech_survey_extra_fields/app_version=19.0",
    "category": "Marketing/Surveys",
    "version": "19.0.1.0",
    "depends": ["survey"],
    "data": [
        "views/survey_question_views.xml",
        "views/survey_templates.xml",
        "data/survey_cron_views.xml",
        "views/survey_survey_cron_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "zehntech_survey_extra_fields/static/src/js/survey_many2many_select2.js",
        ],
        "survey.survey_assets": [
            "zehntech_survey_extra_fields/static/src/js/survey_color_field.js",
            "zehntech_survey_extra_fields/static/src/js/survey_signature_field.js",
            "zehntech_survey_extra_fields/static/src/js/survey_range_field.js",
        ],
    },
    "images": ["static/description/banner.gif"],
    "license": "LGPL-3",
    "price": 15.00,
    "currency": "USD",
    "installable": True,
    "application": True,
    "auto_install": False,
}
