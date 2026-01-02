# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    def _save_lines(self, question, answer, comment=None, overwrite_existing=True):
        """Override to handle custom field types"""
        if question.question_type in ['color', 'email', 'url', 'time', 'range', 'week', 'password', 'file', 'signature', 'month', 'address', 'name', 'many2one', 'many2many']:
            # Handle custom field types as text (char_box)
            old_answers = self.env['survey.user_input.line'].search([
                ('user_input_id', '=', self.id),
                ('question_id', '=', question.id)
            ])
            if old_answers and not overwrite_existing:
                raise UserError(_("This answer cannot be overwritten."))

            # Special handling for many2one to save model,id format
            if question.question_type == 'many2one' and answer and question.many2one_model:
                answer = f"{question.many2one_model},{answer}"

            vals = self._get_line_answer_values(question, answer, 'char_box')

            if old_answers:
                old_answers.write(vals)
                return old_answers
            else:
                return self.env['survey.user_input.line'].create(vals)

        # fallback to super for other question types
        return super()._save_lines(question, answer, comment, overwrite_existing)
