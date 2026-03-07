from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    eagles_assessment_ids = fields.One2many(
        'hr.employee.eagles.assessment',
        'employee_id',
        string='EAGLES Assessments'
    )
    eagles_assessment_count = fields.Integer(
        string='Assessment Count',
        compute='_compute_eagles_assessment_count'
    )

    def _compute_eagles_assessment_count(self):
        for employee in self:
            employee.eagles_assessment_count = len(employee.eagles_assessment_ids)

    def action_open_eagles_survey(self):
        self.ensure_one()

        # Get the survey from config
        survey_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'instix_customisations.eagles_survey_id', default=0
        ))

        if not survey_id:
            raise UserError("No EAGLES Assessment Survey configured. Please set it in Settings.")

        survey = self.env['survey.survey'].sudo().browse(survey_id)

        if not survey.exists():
            raise UserError("The configured EAGLES survey no longer exists. Please reconfigure in Settings.")

        # Create or find existing survey input for this employee
        partner = self.user_id.partner_id if self.user_id else self.work_contact_id

        survey_input = self.env['survey.user_input'].sudo().create({
            'survey_id': survey.id,
            'partner_id': partner.id if partner else False,
            'email': self.work_email,
            'employee_id': self.id,
        })

        if not survey_input:
            survey_input = self.env['survey.user_input'].sudo().create({
                'survey_id': survey.id,
                'partner_id': partner.id if partner else False,
            })

        # Open survey in a new tab / url action
        return {
            'type': 'ir.actions.act_url',
            'url': survey.get_start_url() + '?answer_token=%s' % survey_input.access_token,
            'target': 'new',
        }

class HrEmployeeEaglesAssessment(models.Model):
    _name = 'hr.employee.eagles.assessment'
    _description = 'Employee EAGLES Assessment History'
    _order = 'assessment_date desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    assessment_date = fields.Datetime(string='Assessment Date', required=True, default=fields.Datetime.now)
    pdf_file = fields.Binary(string='PDF Report', required=True)
    pdf_filename = fields.Char(string='Filename', required=True)
    survey_input_id = fields.Many2one('survey.user_input', string='Survey Response', ondelete='set null')

    # Optional: Store summary data for quick reference
    total_score = fields.Float(string='Total Score')
    percentage = fields.Float(string='Percentage')
    player_fit = fields.Char(string='Player Fit')
