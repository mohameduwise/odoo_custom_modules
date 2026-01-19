from odoo import fields, models, _


class SurveyUser_Input(models.Model):
    _inherit = "survey.user_input"

    def _mark_done(self):
        """Handle survey completion and stage transitions"""
        res = super()._mark_done()

        MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB

        for user_input in self:
            applicant = user_input.applicant_id
            if not applicant:
                continue

            job = applicant.job_id
            if not job:
                continue

            current_stage = applicant.stage_id.name
            completed_survey = user_input.survey_id

            # =========================================================
            # 1. VIDEO SURVEY SIZE CHECK
            # =========================================================
            if (job.three_minute_video_survey_id and
                    completed_survey.id == job.three_minute_video_survey_id.id):

                # Find file upload attachments
                attachments = self.env['survey.user_input.line'].search([
                    ('user_input_id', '=', user_input.id),
                    ('question_id.question_type', '=', 'file'),
                    ('attachment_id', '!=', False)
                ])

                total_size = sum(att.attachment_id.file_size or 0 for att in attachments)

                if total_size > MAX_ATTACHMENT_SIZE:
                    fallback_stage = self.env['hr.recruitment.stage'].search([
                        ('name', '=', 'Analytical Skills Screening'),
                        '|',
                        ('job_ids', '=', False),
                        ('job_ids', 'in', [job.id])
                    ], limit=1)

                    if fallback_stage:
                        applicant.write({'stage_id': fallback_stage.id})
                    continue
                else:
                    # Move to next stage if size is OK
                    next_stage = self.env['hr.recruitment.stage'].search([
                        ('name', '=', 'Analytical Skills Screening'),
                        '|',
                        ('job_ids', '=', False),
                        ('job_ids', 'in', [job.id])
                    ], limit=1)

                    if next_stage:
                        applicant.write({'stage_id': next_stage.id})

            # =========================================================
            # 2. ANALYTICAL SKILLS SCREENING → LOGICAL SKILLS SCREENING
            # =========================================================
            elif current_stage == 'Analytical Skills Screening':
                if (completed_survey.id == applicant.analytical_skills_screening_survey_id.id and
                        user_input.state == 'done'):

                    # Check if job has specific passing criteria
                    if (hasattr(job, 'analytical_survey_pass_criteria_enabled') and
                            job.analytical_survey_pass_criteria_enabled):

                        score = user_input.scoring_percentage or 0
                        min_score = job.analytical_survey_passing_score or 0

                        if score >= min_score:
                            next_stage = self.env['hr.recruitment.stage'].search([
                                ('name', '=', 'Logical Skills Screening'),
                                '|',
                                ('job_ids', '=', False),
                                ('job_ids', 'in', [job.id])
                            ], limit=1)

                            if next_stage:
                                applicant.write({'stage_id': next_stage.id})
                    else:
                        # Default behavior - just move forward
                        next_stage = self.env['hr.recruitment.stage'].search([
                            ('name', '=', 'Logical Skills Screening'),
                            '|',
                            ('job_ids', '=', False),
                            ('job_ids', 'in', [job.id])
                        ], limit=1)

                        if next_stage:
                            applicant.write({'stage_id': next_stage.id})

            # =========================================================
            # 3. LOGICAL SKILLS SCREENING → GEMS STONE SCREENING
            # =========================================================
            elif current_stage == 'Logical Skills Screening':
                if (completed_survey.id == applicant.logical_skills_screening_survey_id.id and
                        user_input.state == 'done'):

                    # Find latest completed analytical survey
                    analytical_responses = self.env['survey.user_input'].search([
                        ('survey_id', '=', applicant.analytical_skills_screening_survey_id.id),
                        ('applicant_id', '=', applicant.id),
                        ('state', '=', 'done')
                    ], order='create_date desc', limit=1)

                    if analytical_responses:
                        analytical_score = analytical_responses.scoring_percentage or 0
                        logical_score = user_input.scoring_percentage or 0

                        # Check if job has combined criteria
                        if (hasattr(job, 'analytical_logical_survey_pass_criteria_enabled') and
                                job.analytical_logical_survey_pass_criteria_enabled):

                            analytical_min = job.analytical_survey_passing_score or 0
                            logical_min = job.logical_survey_passing_score or 0

                            if (analytical_score >= analytical_min and
                                    logical_score >= logical_min):

                                next_stage = self.env['hr.recruitment.stage'].search([
                                    ('name', '=', 'GEMS Stone Screening'),
                                    '|',
                                    ('job_ids', '=', False),
                                    ('job_ids', 'in', [job.id])
                                ], limit=1)

                                if next_stage:
                                    applicant.write({'stage_id': next_stage.id})
                            else:
                                if hasattr(applicant, 'action_send_level_2_failed_email'):
                                    applicant.sudo().action_send_level_2_failed_email()
                        else:
                            # Old average-based logic
                            avg_score = (analytical_score + logical_score) / 2
                            if avg_score > 70:
                                next_stage = self.env['hr.recruitment.stage'].search([
                                    ('name', '=', 'GEMS Stone Screening'),
                                    '|',
                                    ('job_ids', '=', False),
                                    ('job_ids', 'in', [job.id])
                                ], limit=1)

                                if next_stage:
                                    applicant.write({'stage_id': next_stage.id})
                            else:
                                if hasattr(applicant, 'action_send_level_2_failed_email'):
                                    applicant.sudo().action_send_level_2_failed_email()

            # =========================================================
            # 4. GEMS STONE SCREENING → OAD IDEAL PROFILE SCREENING
            # =========================================================
            elif current_stage == 'GEMS Stone Screening':
                if (applicant.gems_stone_screening_id and
                        completed_survey.id == applicant.gems_stone_screening_id.id and
                        user_input.state == 'done' and user_input.scoring_total):

                    try:
                        score_int = int(user_input.scoring_total)
                        formatted_score = f"{score_int:08d}"

                        if len(formatted_score) >= 8:
                            sets = [formatted_score[i:i + 2] for i in range(0, 8, 2)]

                            gem_map = {
                                "EMERALD": int(sets[0]),
                                "PEARL": int(sets[1]),
                                "RUBY": int(sets[2]),
                                "SAPPHIRE": int(sets[3]),
                            }

                            sorted_gems = sorted(gem_map.items(), key=lambda x: x[1], reverse=True)

                            if len(sorted_gems) >= 2:
                                primary_gem = sorted_gems[0][0]
                                secondary_gem = sorted_gems[1][0]

                                if (hasattr(job, 'x_studio_primary') and
                                        hasattr(job, 'x_studio_secondary') and
                                        job.x_studio_primary == primary_gem and
                                        job.x_studio_secondary == secondary_gem):

                                    next_stage = self.env['hr.recruitment.stage'].search([
                                        ('name', '=', 'OAD Ideal Profile Screening'),
                                        '|',
                                        ('job_ids', '=', False),
                                        ('job_ids', 'in', [job.id])
                                    ], limit=1)

                                    if next_stage:
                                        applicant.write({'stage_id': next_stage.id})
                    except (ValueError, IndexError):
                        # Silently continue if score parsing fails
                        continue

            # =========================================================
            # 5. 3 MINUTE VIDEO POSTING → ANALYTICAL SKILLS SCREENING
            # =========================================================
            elif current_stage == '3 Minute Video Posting':
                if (job.three_minute_video_survey_id and
                        completed_survey.id == job.three_minute_video_survey_id.id and
                        user_input.state == 'done'):

                    # Check if video was uploaded
                    video_answers = self.env['survey.user_input.line'].search([
                        ('user_input_id', '=', user_input.id),
                        ('question_id.question_type', '=', 'file'),
                        ('attachment_id', '!=', False)
                    ])

                    if video_answers:
                        next_stage = self.env['hr.recruitment.stage'].search([
                            ('name', '=', 'Analytical Skills Screening'),
                            '|',
                            ('job_ids', '=', False),
                            ('job_ids', 'in', [job.id])
                        ], limit=1)

                        if next_stage:
                            applicant.write({'stage_id': next_stage.id})

        return res
    def get_gems_data(self):
        """
        Get GEMS calculation data for template use
        Returns the gems data or False if not applicable
        """
        self.ensure_one()
        if self.survey_id.survey_type != 'recruitment':
            return False
        total_score = self.scoring_total or 0
        if total_score == 0:
            return False
        gems_data = self.survey_id._get_gems_stone_mapping(total_score)
        gems_data['total_score'] = total_score

        return gems_data