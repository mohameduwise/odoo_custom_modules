from odoo import fields, models,api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    eagles_survey_id = fields.Many2one(
        'survey.survey',
        string='EAGLES Assessment Survey',
        help='Select the survey to use for EAGLES assessments',
        config_parameter='instix_customisations.eagles_survey_id'
    )
