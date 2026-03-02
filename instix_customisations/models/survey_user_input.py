import logging

from odoo import fields, models, api, _
from odoo.exceptions import UserError
_logger = logging.getLogger('odoo')


class SurveyUser_Input(models.Model):
    _inherit = "survey.user_input"

    def _mark_done(self):
        """Handle survey completion and stage transitions"""
        res = super()._mark_done()

        MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB

        for user_input in self:
            # =========================================================
            # CHECK IF THIS IS THE EAGLES SURVEY (from settings)
            # =========================================================
            eagles_survey_id = self.env['ir.config_parameter'].sudo().get_param(
                'instix_customisations.eagles_survey_id'
            )

            if eagles_survey_id and user_input.survey_id.id == int(eagles_survey_id):
                # This is an EAGLES assessment - auto-save to employee
                try:
                    user_input.action_save_eagles_report_to_employee()
                except Exception as e:
                    # Log error but don't break the flow
                    _logger = logging.getLogger(__name__)
                    _logger.error(f"Failed to auto-save EAGLES report: {str(e)}")

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
                    if job.analytical_logical_survey_pass_criteria_enabled:
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
                        # If criteria is disabled, just move forward without checking score
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

                        # Check if individual passing criteria is enabled
                        if job.analytical_logical_survey_pass_criteria_enabled:
                            analytical_min = job.analytical_survey_passing_score or 0
                            logical_min = job.logical_survey_passing_score or 0

                            # Both scores must meet their individual criteria
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
                                failed_stage = self.env['hr.recruitment.stage'].search([
                                    ('name', '=', 'Dropped'),
                                    '|',
                                    ('job_ids', '=', False),
                                    ('job_ids', 'in', [job.id])
                                ], limit=1)

                                if failed_stage:
                                    applicant.write({'stage_id': failed_stage.id})

                                    # Failed individual criteria
                                    applicant.action_send_level_2_failed_email(failure_type='assessment')
                        else:
                            # Average-based logic (when criteria is disabled)
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
                                failed_stage = self.env['hr.recruitment.stage'].search([
                                    ('name', '=', 'Dropped'),
                                    '|',
                                    ('job_ids', '=', False),
                                    ('job_ids', 'in', [job.id])
                                ], limit=1)

                                if failed_stage:
                                    applicant.write({'stage_id': failed_stage.id})
                                    applicant.action_send_level_2_failed_email(failure_type='assessment')

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
                                gem_colors = {
                                    "EMERALD": "#2ECC71",
                                    "RUBY": "#E74C3C",
                                    "SAPPHIRE": "#3498DB",
                                    "PEARL": "#DCCCA3",
                                }

                                primary_color = gem_colors.get(primary_gem, "#777")
                                secondary_color = gem_colors.get(secondary_gem, "#777")

                                gemstone_html = f"""
                                <div style="padding:8px;border:1px solid #ddd;border-radius:8px;background:#f9f9f9;color:black;">
                                     <b style="color:black;">Gemstone Result</b><br/>
                                    Primary:
                                    <span style="
                                        background:{primary_color};
                                        color:black !important;
                                        padding:2px 8px;
                                        border-radius:10px;
                                        font-weight:600;
                                    ">
                                        {primary_gem}
                                    </span>
                                    &nbsp;
                                    Secondary:
                                    <span style="
                                        background:{secondary_color};
                                        color:black !important;
                                        padding:2px 8px;
                                        border-radius:10px;
                                        font-weight:600;
                                    ">
                                        {secondary_gem}
                                    </span>
                                </div>
                                """

                                applicant.write({
                                    'gemstone_result_html': gemstone_html
                                })
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

    def action_save_eagles_report_to_employee(self):
        """Auto-save EAGLES assessment PDF to employee record history"""
        self.ensure_one()

        # Get data to verify it's a valid EAGLES assessment
        data = self._get_eagles_data()

        # Check if we have any questions with answers
        has_answers = False
        for cat in data.get('categories', []):
            if cat.get('questions') and any(q.get('score', 0) > 0 for q in cat['questions']):
                has_answers = True
                break

        if not has_answers:
            return False  # Silently skip if no answers

        # Find employee based on survey data
        employee = False

        # Try to find employee by email from survey
        if data.get('email'):
            employee = self.env['hr.employee'].search([
                ('work_email', '=', data['email'])
            ], limit=1)

        # If not found, try by name
        if not employee and data.get('name'):
            employee = self.env['hr.employee'].search([
                ('name', 'ilike', data['name'])
            ], limit=1)

        # If still not found, try by current user
        if not employee:
            employee = self.env.user.employee_id

        if not employee:
            return False  # Silently skip if no employee found

        # Generate PDF report
        report_action = self.env.ref('instix_customisations.action_eagles_assessment_report')

        # Render PDF
        pdf_content, report_format = self.env['ir.actions.report']._render_qweb_pdf(
            report_action.report_name,
            self.ids
        )

        if pdf_content:
            import base64
            import logging
            _logger = logging.getLogger(__name__)

            pdf_base64 = base64.b64encode(pdf_content)

            # Create filename with timestamp
            timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"EAGLES_Assessment_{employee.name}_{timestamp}.pdf"

            # Create history record instead of overwriting
            assessment = self.env['hr.employee.eagles.assessment'].create({
                'employee_id': employee.id,
                'assessment_date': fields.Datetime.now(),
                'pdf_file': pdf_base64,
                'pdf_filename': filename,
                'survey_input_id': self.id,
                'total_score': data.get('total_score', 0),
                'percentage': data.get('percentage', 0),
                'player_fit': data.get('player_fit', ''),
            })

            _logger.info(f"Saved EAGLES assessment #{assessment.id} for employee {employee.name}")
            return True

        return False

    def _get_eagles_data(self):
        self.ensure_one()

        import re
        import base64
        import os

        # ── Helper: strip emojis and non-ASCII decorations ────────────
        def clean_title(text):
            # Remove emoji / non-ASCII unicode characters
            text = re.sub(r'[^\x00-\x7F]+', '', text)
            # Collapse multiple spaces left behind after emoji removal
            text = re.sub(r'\s{2,}', ' ', text)
            return text.strip()

        # ── Helper: strip leading key prefix from section label ───────
        # After emoji removal, "🔥 E – ENGAGEMENT" becomes "E ENGAGEMENT"
        # (the en-dash and emoji are both stripped as non-ASCII, leaving a
        # space between the letter code and the name).
        # Strip the leading 1-4 uppercase letters + space so the label
        # becomes just "ENGAGEMENT" — preventing "E . E ENGAGEMENT".
        def strip_key_prefix(text):
            cleaned = re.sub(r'^[A-Z]{1,4}\s+', '', text).strip()
            return cleaned if cleaned else text

        # ── 1. Participant details from survey ─────────────────────
        name = email = phone = ''
        for line in self.user_input_line_ids:
            q_title = (line.question_id.title or '').strip().lower()
            value = (line.value_char_box or '').strip()
            if 'full name' in q_title or q_title == 'name':
                name = value
            elif 'email' in q_title:
                email = value
            elif 'phone' in q_title:
                phone = value

        # ── 2. Fallback to employee record ──────────────────────────
        if not (name and email and phone):
            employee = self.env.user.employee_id
            if employee:
                if not name:
                    name = employee.name or ''
                if not email:
                    email = employee.work_email or ''
                if not phone:
                    phone = employee.phone or employee.mobile_phone or ''

        # ── 3. Get ALL survey questions in order ────────────────────
        all_questions = self.env['survey.question'].search(
            [('survey_id', '=', self.survey_id.id)],
            order='sequence asc'
        )

        # ── 4. Build answer map ─────────────────────────────────────
        answer_map = {}
        for line in self.user_input_line_ids:
            if line.question_id:
                answer_map[line.question_id.id] = line

        # ── 5. Question types that carry scorable/displayable answers ─
        # simple_choice / multiple_choice → scored options
        # char_box / text_box             → free-text answers (score=0 but still show)
        SCORED_TYPES   = ('simple_choice', 'multiple_choice')
        FREETEXT_TYPES = ('char_box', 'text_box')
        ALL_DISPLAY_TYPES = SCORED_TYPES + FREETEXT_TYPES

        # ── 6. Sections to silently skip (non-scoring intro pages) ───
        SKIP_SECTION_KEYWORDS = {
            'team member details',
            'participant details',
            'personal details',
            'introduction',
            'instructions',
        }

        SKIP_QUESTION_TITLES = {
            'full name', 'email address', 'phone number',
            'name', 'email', 'phone',
        }

        # ── 7. Walk questions — dynamic section discovery ────────────
        categories = []
        current_cat = None
        seen_keys = {}   # base_key → count, for dedup (E, E2, E3…)

        for question in all_questions:
            raw_title = (question.title or '').strip()

            # ── Page / section header ──────────────────────────────
            if question.is_page:
                if not raw_title:
                    current_cat = None
                    continue

                clean = clean_title(raw_title)

                # Skip known non-assessment sections
                if any(kw in clean.lower() for kw in SKIP_SECTION_KEYWORDS):
                    current_cat = None
                    continue

                # Strip leading key prefix so "E - ENGAGEMENT" → "ENGAGEMENT"
                display_label = strip_key_prefix(clean)

                # Build short key from first letter of cleaned title
                base_key = clean[0].upper() if clean else 'X'
                seen_keys[base_key] = seen_keys.get(base_key, 0) + 1
                count = seen_keys[base_key]
                key = base_key if count == 1 else f"{base_key}{count}"

                current_cat = {
                    'key': key,
                    'label': display_label,   # clean label WITHOUT the leading letter
                    'questions': [],
                    'total': 0.0,
                }
                categories.append(current_cat)
                continue

            # ── Skip personal-detail questions ─────────────────────
            if raw_title.lower() in SKIP_QUESTION_TITLES:
                continue

            # ── Only displayable question types ────────────────────
            if question.question_type not in ALL_DISPLAY_TYPES:
                continue

            # ── Assign to current category ──────────────────────────
            if current_cat is not None:
                line = answer_map.get(question.id)
                answer_text = ''
                score = 0.0

                if line:
                    if question.question_type in SCORED_TYPES:
                        # Choice question — use selected option + its score
                        if line.suggested_answer_id:
                            answer_text = line.suggested_answer_id.value or ''
                            score = float(line.suggested_answer_id.answer_score or 0.0)
                    elif question.question_type in FREETEXT_TYPES:
                        # Free-text question — show the typed answer, score = 0
                        answer_text = (line.value_char_box or line.value_text_box or '').strip()

                current_cat['questions'].append({
                    'title': clean_title(raw_title),
                    'answer': answer_text,
                    'score': score,
                })
                current_cat['total'] += score

        # ── 8. Remove sections with zero questions ───────────────────
        categories = [c for c in categories if c['questions']]

        # ── 9. Max score (choice questions only) ─────────────────────
        max_score = 0.0
        for question in all_questions:
            if question.question_type in SCORED_TYPES and not question.is_page:
                scores = [
                    float(s.answer_score or 0)
                    for s in question.suggested_answer_ids
                    if s.answer_score
                ]
                if scores:
                    max_score += max(scores)

        # ── 10. Total & Player Fit ────────────────────────────────────
        total_score = sum(c['total'] for c in categories)
        percentage = round((total_score / max_score * 100), 1) if max_score else 0.0

        PLAYER_FIT = [
            (85, 100, 'A Player', '#2e7d32'),
            (70,  84, 'B Player', '#1565c0'),
            (50,  69, 'C Player', '#e65100'),
            (0,   49, 'D Player', '#b71c1c'),
        ]
        player_fit = 'D Player'
        player_color = '#b71c1c'
        for low, high, label, color in PLAYER_FIT:
            if low <= percentage <= high:
                player_fit = label
                player_color = color
                break

        # ── 11. Bar data (scored categories only — skip free-text-only sections) ─
        bar_data = []
        for cat in categories:
            # Only include in chart if at least one question has a score > 0 possible
            bar_data.append({
                'label': cat['key'],
                'full_label': cat['label'],
                'score': cat['total'],
            })

        # ── 12. Logo as base64 ───────────────────────────────────────
        logo_b64 = ''
        try:
            img_path = os.path.join(os.path.dirname(__file__), '../static/src/img/icon.png')
            with open(img_path, 'rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            pass

        return {
            'name': name,
            'email': email,
            'phone': phone,
            'categories': categories,
            'total_score': total_score,
            'max_score': max_score,
            'percentage': percentage,
            'player_fit': player_fit,
            'player_color': player_color,
            'bar_data': bar_data,
            'logo_b64': logo_b64,
        }
    def action_print_eagles_report(self):
        """Button action to print the EAGLES PDF report."""
        self.ensure_one()
        return self.env.ref(
            'instix_customisations.action_eagles_assessment_report'
        ).report_action(self)

    def get_gems_data(self):
        """
        Get GEMS calculation data for template use
        Returns the gems data or False if not applicable
        """
        self.ensure_one()
        if self.survey_id.survey_type != 'recruitment':
            return False
        if not self.applicant_id or not self.applicant_id.job_id:
            return False
        job = self.applicant_id.job_id
        # Check if this is the gemstone screening survey for this job
        if not job.gems_stone_screening_id or self.survey_id.id != job.gems_stone_screening_id.id:
            return False
        total_score = self.scoring_total or 0
        if total_score == 0:
            return False
        gems_data = self.survey_id._get_gems_stone_mapping(total_score)
        gems_data['total_score'] = total_score
        return gems_data


class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    attachment_id = fields.Many2one('ir.attachment', 'Attachment')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            question = record.question_id
            attachment = record.value_char_box  # assuming this holds attachment id or record

            if not (question and attachment):
                continue

            # Check if question type is file upload
            if question.question_type != 'file':
                continue

            # Assign attachment
            record.attachment_id = int(attachment)

        return records

    def action_download_attachment(self):
        """ Download the XML file linked to the document. """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
        }
