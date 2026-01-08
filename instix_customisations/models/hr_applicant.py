from odoo import models, fields,_
from odoo.exceptions import UserError
from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import re
import logging
from io import BytesIO
import pdfplumber
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

_logger = logging.getLogger(__name__)

nltk.download('stopwords')
nltk.download('wordnet')



class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    ic_passport_copy = fields.Binary(string="IC / Passport Copy")
    resume_attachment = fields.Binary(string="Resume (Attachment)")
    degree_certificate = fields.Binary(string="Degree Certificate")
    other_certificate = fields.Binary(string="Other Courses Certificate")
    analytical_skills_screening_survey_id = fields.Many2one('survey.survey', related='job_id.analytical_skills_screening_survey_id', string="Analytical Skills Screening Survey", readonly=True)
    logical_skills_screening_survey_id = fields.Many2one('survey.survey', related='job_id.logical_skills_screening_survey_id', string="Logical Skills Screening Survey", readonly=True)
    gems_stone_screening_id = fields.Many2one('survey.survey', related='job_id.gems_stone_screening_id', string="GEMS Stone Screening Survey", readonly=True)
    resume = fields.Binary(string="Resume")
    stage_name = fields.Char(related='stage_id.name')

    ai_score = fields.Float(string="AI Resume Score", readonly=True)
    ai_score_range = fields.Selection([
        ('excellent', 'Excellent'),
        ('great', 'Great '),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor '),
        ('not_scored', 'Not Scored'),
    ], compute="_compute_ai_score_range", string="Efficiency",store=True)

    resume_text = fields.Text(readonly=True)
    ai_score_breakdown = fields.Text(readonly=True)

    # ------------------------------------------------------------
    # COMPUTE SCORE RANGE
    # ------------------------------------------------------------
    @api.depends('ai_score')
    def _compute_ai_score_range(self):
        for rec in self:
            if not rec.ai_score:
                rec.ai_score_range = 'not_scored'
            elif rec.ai_score >= 90:
                rec.ai_score_range = 'excellent'
            elif rec.ai_score >= 80:
                rec.ai_score_range = 'great'
            elif rec.ai_score >= 70:
                rec.ai_score_range = 'good'
            elif rec.ai_score >= 50:
                rec.ai_score_range = 'fair'
            else:
                rec.ai_score_range = 'poor'

    # ------------------------------------------------------------
    # BUTTON ACTION
    # ------------------------------------------------------------
    def action_score_resume(self):
        for applicant in self:
            if not applicant.resume:
                raise UserError("Please upload a resume first.")

            resume_text = applicant._extract_resume_text()
            score = round(applicant._calculate_ai_score(resume_text), 2)

            applicant.write({
                'resume_text': resume_text,
                'ai_score': score,
            })
            applicant._auto_move_to_qualified_stage()

    def _auto_move_to_qualified_stage(self):
        self.ensure_one()

        if not self.job_id or not self.ai_score:
            return

        required_score = self.job_id.resume_pass_score or 0
        if self.ai_score < required_score:
            return

        stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Qualified Resume'),
            '|',
            ('job_ids', 'in', self.job_id.id),
            ('job_ids', '=', False)
        ], limit=1)

        if stage and self.stage_id != stage:
            self.stage_id = stage.id

    def _extract_resume_text(self):
        self.ensure_one()
        try:
            resume_bytes = base64.b64decode(self.resume)
            with pdfplumber.open(BytesIO(resume_bytes)) as pdf:
                text = "".join(page.extract_text() or "" for page in pdf.pages)

            if not text.strip():
                raise UserError("No readable text found in the resume.")

            return text

        except Exception as e:
            _logger.error("Resume parsing failed: %s", str(e))
            raise UserError("Unable to extract text from the resume.")

    def _calculate_ai_score(self, resume_text):
        lemmatizer = WordNetLemmatizer()

        resume_words = set(
            lemmatizer.lemmatize(w)
            for w in re.findall(r'\w+', resume_text.lower())
        )
        breakdown = {}

        # ======================================================
        # 1️⃣ SKILLS MATCH — PRIMARY SIGNAL (MAX 45)
        # ======================================================
        skill_score = 0
        job_skills = []

        if self.job_id.resume_skill_ids:
            job_skills = [
                lemmatizer.lemmatize(s.name.lower())
                for s in self.job_id.resume_skill_ids and self.job_id.resume_keyword_ids
            ]

        if job_skills:
            hits = sum(1 for s in job_skills if s in resume_words)
            ratio = hits / len(job_skills)

            if ratio >= 0.9:
                skill_score = 50
            elif ratio >= 0.75:
                skill_score = 44
            elif ratio >= 0.6:
                skill_score = 38
            elif ratio >= 0.45:
                skill_score = 32
            elif ratio >= 0.3:
                skill_score = 26
            elif ratio >= 0.2:
                skill_score = 20
            elif ratio >= 0.1:
                skill_score = 14
            else:
                skill_score = 8
            if hits >= 5:
                skill_score += 2
            if hits >= 8:
                skill_score += 3

        else:
            # No skills configured → neutral (never punish)
            skill_score = 28

        skill_score = min(skill_score, 50)
        breakdown['Skills Match'] = skill_score

        # ======================================================
        # 2️⃣ EXPERIENCE FIT — RELEVANT YEARS (MAX 20)
        # ======================================================
        years = self._extract_years_experience(resume_text)
        min_exp = self.job_id.resume_min_experience or 0
        max_exp = self.job_id.resume_max_experience or 0

        if min_exp and years < min_exp:
            gap = min_exp - years
            experience_score = max(8, 16 - gap * 2)
        elif max_exp and years > max_exp:
            experience_score = 20
        else:
            experience_score = 22

        breakdown['Experience Fit'] = experience_score

        # ======================================================
        # 3️⃣ STRUCTURE / ATS COMPATIBILITY (MAX 15)
        # ======================================================
        structure_ratio = self._evaluate_structure(resume_text)
        structure_score = round(structure_ratio * 15, 2)

        breakdown['Structure / ATS'] = structure_score
        ai_bonus = self._get_ai_bonus(resume_text) or 7
        breakdown['AI Semantic Bonus'] = ai_bonus

        # ======================================================
        # FINAL SCORE
        # ======================================================
        total_score = sum(breakdown.values())

        self.ai_score_breakdown = "\n".join(
            f"{k}: {v}" for k, v in breakdown.items()
        )

        return round(min(total_score, 100), 2)

    # ------------------------------------------------------------
    # AI BONUS (MAX 5 POINTS – SAFE)
    # ------------------------------------------------------------
    def _get_ai_bonus(self, resume_text):
        ai_model = self.env['resume.ai.model'].search(
            [('active', '=', True)], limit=1
        )

        if not ai_model or not ai_model.model_data:
            return 0

        try:
            model = ai_model.get_model()
            prob = model.predict_proba([resume_text])[0][1]
            return round(prob * 10, 2)  or 5
        except Exception:
            return 0

    def _extract_years_experience(self, text):
        match = re.search(r'(\d+)\+?\s*years?', text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _evaluate_structure(self, text):
        sections = [
            'experience', 'education', 'skills',
            'summary', 'projects', 'certifications'
        ]
        text = text.lower()
        found = sum(1 for s in sections if s in text)
        return min(found / len(sections), 1.0)

    def action_send_analytical_skills_survey(self):
        self.ensure_one()
        odoobot = self.env.ref('base.partner_root')
        # if an applicant does not already has associated partner_id create it
        if not self.partner_id:
            if not self.partner_name:
                raise UserError(_('Please provide an applicant name.'))
            self.partner_id = self.env['res.partner'].sudo().create({
                'is_company': False,
                'name': self.partner_name,
                'email': self.email_from,
                'phone': self.partner_phone,
            })

        self.analytical_skills_screening_survey_id.check_validity()
        template = self.env.ref('instix_customisations.email_analytical_test', raise_if_not_found=False)

        invite = self.env['survey.invite'].create({
            'survey_id': self.analytical_skills_screening_survey_id.id,
            'partner_ids': [(6, 0, self.partner_id.ids)],
            'applicant_id': self.id,
            'template_id': template.id if template else False,
            'deadline': fields.Datetime.now() + timedelta(days=15),
        })

        # 2️⃣ Call invite action (send email + create user_input)
        invite.with_user(odoobot).action_invite()

        return True
    


    def action_send_logical_skills_survey(self):
        self.ensure_one()
        odoobot = self.env.ref('base.partner_root')
        # if an applicant does not already has associated partner_id create it
        if not self.partner_id:
            if not self.partner_name:
                raise UserError(_('Please provide an applicant name.'))
            self.partner_id = self.env['res.partner'].sudo().create({
                'is_company': False,
                'name': self.partner_name,
                'email': self.email_from,
                'phone': self.partner_phone,
            })

        self.logical_skills_screening_survey_id.check_validity()
        template = self.env.ref('instix_customisations.email_logical_test', raise_if_not_found=False)

        invite = self.env['survey.invite'].create({
            'survey_id': self.logical_skills_screening_survey_id.id,
            'partner_ids': [(6, 0, self.partner_id.ids)],
            'applicant_id': self.id,
            'template_id': template.id if template else False,
            'deadline': fields.Datetime.now() + timedelta(days=15),
        })
        
        # 2️⃣ Call invite action (send email + create user_input)
        invite.with_user(odoobot).action_invite()

        return True
    


    def action_send_gems_stone_survey(self):
        self.ensure_one()
        odoobot = self.env.ref('base.partner_root')
        # if an applicant does not already has associated partner_id create it
        if not self.partner_id:
            if not self.partner_name:
                raise UserError(_('Please provide an applicant name.'))
            self.partner_id = self.env['res.partner'].sudo().create({
                'is_company': False,
                'name': self.partner_name,
                'email': self.email_from,
                'phone': self.partner_phone,
            })

        self.gems_stone_screening_id.check_validity()
        template = self.env.ref('instix_customisations.email_gemstone_test', raise_if_not_found=False)

        invite = self.env['survey.invite'].create({
            'survey_id': self.gems_stone_screening_id.id,
            'partner_ids': [(6, 0, self.partner_id.ids)],
            'applicant_id': self.id,
            'template_id': template.id if template else False,
            'deadline': fields.Datetime.now() + timedelta(days=15),
        })

        # 2️⃣ Call invite action (send email + create user_input)
        invite.with_user(odoobot).action_invite()

        return True
    

    def action_send_level_2_failed_email(self):
        self.ensure_one()
        odoobot = self.env.ref('base.partner_root')
        # XML ID of the email template
        template = self.env.ref('instix_customisations.email_level_2_failed', raise_if_not_found=False)

        if template:
            template.with_user(odoobot).send_mail(
                self.id,
                force_send=True,   # Send immediately
            )

    def action_open_link_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Link',
            'res_model': 'hr.applicant.oad.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_id': self.id,
            }
        }

class HRSkill(models.Model):
    _name = 'resume.skill'
    _description = 'HR Skill'

    name = fields.Char(required=True)
