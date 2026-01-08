# -*- coding: utf-8 -*-
{
    'name': 'AI Resume Analyzer and Screening for Odoo',
    'version': '1.0',
    'category': 'Human Resources/Recruitment',
    'summary': 'AI-powered resume analyzer and screening system for Odoo recruitment',
    'description': """
        AI Resume Analyzer and Screening for Odoo
        
        This comprehensive module adds AI-powered resume analysis and screening capabilities to Odoo's recruitment process.
        
        Key Features:
        - Intelligent resume parsing and text extraction from PDF files
        - Automatic resume scoring based on job requirements (0-100 scale)
        - Keyword matching with advanced lemmatization
        - Experience extraction and validation
        - Machine learning model for intelligent resume evaluation
        - Automated screening and scoring workflows
        - Email notifications for high-scoring candidates
        - ATS-compatible resume structure evaluation
        - Kanban and list views for easy management
        - Comprehensive demo data for testing
        
        Perfect for HR teams looking to streamline their recruitment process with AI-powered automation.
    """,
    'author': 'Webbycrown Solutions',
    'website': 'www.webbycrown.com',
    'license': 'LGPL-3',
    'depends': ['hr_recruitment', 'hr', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/email_template_data.xml',
        'views/resume_screening.xml',
    ],
    'images': ['static/description/main_screenshot.png'],
    'icon': 'pharmacy_management_system/static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'external_dependencies': {
        'python': ['scikit-learn'],
    },
    'assets': {
        'web.assets_backend': [
            'ai_resume_analyzer_screening_odoo/static/src/**/*.js',
            'ai_resume_analyzer_screening_odoo/static/src/**/*.xml',
        ],
    },
}