from odoo import fields, models, _


class SurveyUser_Input(models.Model):
    _inherit = "survey.user_input"


    def _mark_done(self):
        res = super()._mark_done()
        for user_input in self:
            if user_input.applicant_id:
                if user_input.applicant_id.stage_id.name == 'Analytical Skills Screening':
                    sorted_interviews = user_input.applicant_id.response_ids\
                        .filtered(lambda i: i.survey_id == user_input.applicant_id.analytical_skills_screening_survey_id)\
                        .sorted(lambda i: i.create_date, reverse=True)
                    if sorted_interviews:
                        answered_interviews = sorted_interviews.filtered(lambda i: i.state == 'done')
                        if answered_interviews:
                            next_stage = self.env['hr.recruitment.stage'].search([
                                    ('name', '=', 'Logical Skills Screening')
                                ], limit=1)
                            if next_stage:
                                user_input.applicant_id.with_user(user_input.applicant_id.user_id).write({
                                                'stage_id': next_stage.id
                                            })

                elif user_input.applicant_id.stage_id.name == 'Logical Skills Screening':
                    sorted_interviews_logic = user_input.applicant_id.response_ids\
                        .filtered(lambda i: i.survey_id == user_input.applicant_id.logical_skills_screening_survey_id)\
                        .sorted(lambda i: i.create_date, reverse=True)
                    if sorted_interviews_logic:
                        answered_interviews_logic = sorted_interviews_logic.filtered(lambda i: i.state == 'done')
                    sorted_interviews = user_input.applicant_id.response_ids\
                        .filtered(lambda i: i.survey_id == user_input.applicant_id.analytical_skills_screening_survey_id)\
                        .sorted(lambda i: i.create_date, reverse=True)
                    if sorted_interviews:
                        answered_interviews = sorted_interviews.filtered(lambda i: i.state == 'done')
                    if answered_interviews_logic and answered_interviews:
                        if (answered_interviews_logic[0].scoring_percentage + answered_interviews[0].scoring_percentage)/2 > 70:
                            next_stage = self.env['hr.recruitment.stage'].search([
                                    ('name', '=', 'GEMS Stone Screening')
                                ], limit=1)
                            if next_stage:
                                user_input.applicant_id.with_user(user_input.applicant_id.user_id).write({
                                                'stage_id': next_stage.id
                                            })
                        else:
                            user_input.applicant_id.sudo().action_send_level_2_failed_email()
                elif user_input.applicant_id.stage_id.name == 'GEMS Stone Screening':
                    sorted_interviews = user_input.applicant_id.response_ids\
                        .filtered(lambda i: i.survey_id == user_input.applicant_id.gems_stone_screening_id)\
                        .sorted(lambda i: i.create_date, reverse=True)
                    if sorted_interviews:
                        answered_interviews = sorted_interviews.filtered(lambda i: i.state == 'done')
                        if answered_interviews and answered_interviews[0].scoring_total:
                            score_int = int(answered_interviews[0].scoring_total)

                            formatted_score = f"{score_int:08d}"

                            sets = [formatted_score[i:i+2] for i in range(0, 8, 2)]

                            gem_map = {
                                "EMERALD": int(sets[0]),
                                "PEARL": int(sets[1]),
                                "RUBY": int(sets[2]),
                                "SAPPHIRE": int(sets[3]),
                            }
                            sorted_gems = sorted(gem_map.items(), key=lambda x: x[1], reverse=True)

                            primary_gem = sorted_gems[0][0]
                            secondary_gem = sorted_gems[1][0]
                            if user_input.applicant_id.job_id.x_studio_primary == primary_gem and user_input.applicant_id.job_id.x_studio_secondary == secondary_gem:
                                next_stage = self.env['hr.recruitment.stage'].search([
                                        ('name', '=', 'OAD Ideal Profile Screening')
                                    ], limit=1)
                                if next_stage:
                                    user_input.applicant_id.with_user(user_input.applicant_id.user_id).write({
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