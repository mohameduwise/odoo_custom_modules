from odoo import fields, models, _


class SurveyUser_Input(models.Model):
    _inherit = "survey.user_input"

    def _mark_done(self):
        res = super()._mark_done()

        MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB

        for user_input in self:
            applicant = user_input.applicant_id
            if not applicant:
                continue

            job = applicant.job_id
            if not job:
                continue

            # =========================================================
            # 🔍 CHECK ATTACHMENT SIZE
            # ONLY FOR 3-MINUTE VIDEO SURVEY
            # =========================================================
            if (
                    job.three_minute_video_survey_id
                    and user_input.survey_id == job.three_minute_video_survey_id
            ):
                attachments = self.env['ir.attachment'].search([
                    ('res_model', '=', 'survey.user_input'),
                    ('res_id', '=', user_input.id),
                ])

                total_size = sum(attachments.mapped('file_size') or [0])

                if total_size > MAX_ATTACHMENT_SIZE:
                    _logger.warning(
                        "3-Minute Video Survey attachment size (%s bytes) exceeds limit "
                        "for applicant %s. Moving back to Analytical Skills Screening.",
                        total_size, applicant.id
                    )

                    fallback_stage = self.env['hr.recruitment.stage'].search([
                        ('name', '=', 'Analytical Skills Screening'),
                        '|',
                        ('job_ids', 'in', job.id),
                        ('job_ids', '=', False)
                    ], limit=1)

                    if fallback_stage:
                        applicant.with_user(applicant.user_id).write({
                            'stage_id': fallback_stage.id
                        })
                    continue

            # =========================================================
            # ANALYTICAL SKILLS SCREENING → LOGICAL SKILLS SCREENING
            # =========================================================
            if applicant.stage_id.name == 'Analytical Skills Screening':

                analytical_responses = applicant.response_ids.filtered(
                    lambda r: r.survey_id == applicant.analytical_skills_screening_survey_id
                ).sorted(lambda r: r.create_date, reverse=True)

                if analytical_responses:
                    answered = analytical_responses.filtered(lambda r: r.state == 'done')
                    if answered:
                        next_stage = self.env['hr.recruitment.stage'].search([
                            ('name', '=', 'Logical Skills Screening')
                        ], limit=1)
                        if next_stage:
                            applicant.with_user(applicant.user_id).write({
                                'stage_id': next_stage.id
                            })

            # =========================================================
            # LOGICAL SKILLS SCREENING → GEMS STONE SCREENING
            # =========================================================
            elif applicant.stage_id.name == 'Logical Skills Screening':

                # Latest analytical response
                analytical_responses = applicant.response_ids.filtered(
                    lambda r: r.survey_id == applicant.analytical_skills_screening_survey_id
                ).sorted(lambda r: r.create_date, reverse=True)

                # Latest logical response
                logical_responses = applicant.response_ids.filtered(
                    lambda r: r.survey_id == applicant.logical_skills_screening_survey_id
                ).sorted(lambda r: r.create_date, reverse=True)

                if not analytical_responses or not logical_responses:
                    continue

                analytical_done = analytical_responses.filtered(lambda r: r.state == 'done')
                logical_done = logical_responses.filtered(lambda r: r.state == 'done')

                if not analytical_done or not logical_done:
                    continue

                analytical_score = analytical_done[0].scoring_percentage or 0.0
                logical_score = logical_done[0].scoring_percentage or 0.0

                # ---------------------------------------------------------
                # ✅ NEW: Job-based passing criteria
                # ---------------------------------------------------------
                if job.analytical_logical_survey_pass_criteria_enabled:

                    analytical_pass = analytical_score >= (job.analytical_survey_passing_score or 0)
                    logical_pass = logical_score >= (job.logical_survey_passing_score or 0)

                    if analytical_pass and logical_pass:
                        next_stage = self.env['hr.recruitment.stage'].search([
                            ('name', '=', 'GEMS Stone Screening')
                        ], limit=1)
                        if next_stage:
                            applicant.with_user(applicant.user_id).write({
                                'stage_id': next_stage.id
                            })
                    else:
                        applicant.sudo().action_send_level_2_failed_email()

                # ---------------------------------------------------------
                # 🔁 EXISTING FLOW (UNCHANGED)
                # ---------------------------------------------------------
                else:
                    avg_score = (analytical_score + logical_score) / 2
                    if avg_score > 70:
                        next_stage = self.env['hr.recruitment.stage'].search([
                            ('name', '=', 'GEMS Stone Screening')
                        ], limit=1)
                        if next_stage:
                            applicant.with_user(applicant.user_id).write({
                                'stage_id': next_stage.id
                            })
                    else:
                        applicant.sudo().action_send_level_2_failed_email()

            # =========================================================
            # GEMS STONE SCREENING → OAD IDEAL PROFILE SCREENING
            # =========================================================
            elif applicant.stage_id.name == 'GEMS Stone Screening':

                gems_responses = applicant.response_ids.filtered(
                    lambda r: r.survey_id == applicant.gems_stone_screening_id
                ).sorted(lambda r: r.create_date, reverse=True)

                if gems_responses:
                    answered = gems_responses.filtered(lambda r: r.state == 'done')
                    if answered and answered[0].scoring_total:

                        score_int = int(answered[0].scoring_total)
                        formatted_score = f"{score_int:08d}"
                        sets = [formatted_score[i:i + 2] for i in range(0, 8, 2)]

                        gem_map = {
                            "EMERALD": int(sets[0]),
                            "PEARL": int(sets[1]),
                            "RUBY": int(sets[2]),
                            "SAPPHIRE": int(sets[3]),
                        }

                        sorted_gems = sorted(gem_map.items(), key=lambda x: x[1], reverse=True)
                        primary_gem = sorted_gems[0][0]
                        secondary_gem = sorted_gems[1][0]

                        if (
                                job.x_studio_primary == primary_gem
                                and job.x_studio_secondary == secondary_gem
                        ):
                            next_stage = self.env['hr.recruitment.stage'].search([
                                ('name', '=', 'OAD Ideal Profile Screening')
                            ], limit=1)
                            if next_stage:
                                applicant.with_user(applicant.user_id).write({
                                    'stage_id': next_stage.id
                                })

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