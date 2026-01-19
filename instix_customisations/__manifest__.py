{
    "name": "INSTIX Recruitment Workflow Customisations",
    "summary": "Advanced recruitment workflow with multi-stage screening and automated emails",
    "description": """
This module extends Odoo Recruitment to support a complete
multi-stage hiring workflow including:

- Website job application enhancements
- Resume shortlisting workflow
- Analytical, Logical, Gemstone and OAD personality screening
- Automated email notifications at each recruitment stage
- Score-based screening and progression
- Custom document attachments and applicant data collection

Designed for enterprise hiring workflows with manual HR control.
    """,

    "author": "INSTIX",
    "website": "https://www.instix.com",

    "category": "Human Resources",
    "version": "19.0.9",
    "license": "LGPL-3",

    "depends": [
        "base",
        "mail",
        "hr_recruitment",
        "website_hr_recruitment",
        "survey",
        "hr",
    ],

    "data": [
        "security/ir.model.access.csv",
        'data/data.xml',
        "views/email_templates.xml",
        "views/websie_job_views_inherit.xml",
        "views/hr_applicant_inherit.xml",
        "views/hr_job_views.xml",
        "views/survey_template.xml",
        "wizard/oda_link_view.xml",
		"views/resume_ai_model_views.xml",
],

    'assets': {
        
        "web.assets_frontend": [
            'instix_customisations/static/src/js/website_form_no_file_validation.js'
        ]
    },

    "installable": True,
    "application": False,
    "auto_install": False,
}
