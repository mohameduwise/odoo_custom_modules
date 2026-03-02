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
