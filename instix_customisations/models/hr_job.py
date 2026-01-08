from odoo import models, fields


class HrJob(models.Model):
    _inherit = 'hr.job'

    analytical_skills_screening_survey_id = fields.Many2one(
        'survey.survey',
        domain=[('survey_type', '=', 'recruitment')],
        string='Analytical Skills Screening Survey'
    )

    logical_skills_screening_survey_id = fields.Many2one(
        'survey.survey',
        domain=[('survey_type', '=', 'recruitment')],
        string='Logical Skills Screening Survey'
    )

    gems_stone_screening_id = fields.Many2one(
        'survey.survey',
        domain=[('survey_type', '=', 'recruitment')],
        string='GEMS Stone Screening Survey'
    )
    resume_min_experience = fields.Integer(
        string="Minimum Experience (Years)",
        help="Minimum years of experience expected for this role"
    )

    resume_max_experience = fields.Integer(
        string="Maximum Experience (Years)",
        help="Maximum years of experience preferred for this role"
    )

    resume_pass_score = fields.Float(
        string="Resume Pass Score",
        default=70.0,
        help="Minimum AI resume score required to qualify"
    )

    resume_notes = fields.Text(
        string="Resume Screening Notes",
        help="Internal notes or expectations for resume screening"
    )
    resume_skill_ids = fields.Many2many(
        'resume.skill',
        'hr_job_skill_rel',
        'job_id',
        'skill_id',
        string="Required Skills",
        help="Skills required for this job"
    )
    resume_keyword_ids = fields.Many2many(
        'resume.skill',
        'hr_job_keyword_rel',
        'job_id',
        'keyword_id',
        string="Resume Keywords",
        help="Keywords expected to appear in resumes"
    )
