import base64
import logging
import nltk
import pdfplumber
import re
from datetime import timedelta
from io import BytesIO
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

from odoo import models, fields, _
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
nltk.download('stopwords')
nltk.download('wordnet')
from collections import Counter
from difflib import SequenceMatcher


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    # Existing fields
    ic_passport_copy = fields.Binary(string="IC / Passport Copy")
    resume_attachment = fields.Binary(string="Resume (Attachment)")
    degree_certificate = fields.Binary(string="Degree Certificate")
    other_certificate = fields.Binary(string="Other Courses Certificate")
    three_minute_video_survey_id = fields.Many2one(
        'survey.survey',
        related='job_id.three_minute_video_survey_id',
        string="3 Minute Video Screening Survey",
        readonly=True
    )
    analytical_skills_screening_survey_id = fields.Many2one(
        'survey.survey',
        related='job_id.analytical_skills_screening_survey_id',
        string="Analytical Skills Screening Survey",
        readonly=True
    )
    logical_skills_screening_survey_id = fields.Many2one(
        'survey.survey',
        related='job_id.logical_skills_screening_survey_id',
        string="Logical Skills Screening Survey",
        readonly=True
    )
    gems_stone_screening_id = fields.Many2one(
        'survey.survey',
        related='job_id.gems_stone_screening_id',
        string="GEMS Stone Screening Survey",
        readonly=True
    )
    resume = fields.Binary(string="Resume")
    stage_name = fields.Char(related='stage_id.name')

    # AI Scoring fields
    ai_score = fields.Float(string="AI Resume Score", readonly=True)
    ai_score_range = fields.Selection([
        ('excellent', 'Excellent (90-100)'),
        ('great', 'Great (80-89)'),
        ('good', 'Good (70-79)'),
        ('fair', 'Fair (50-69)'),
        ('poor', 'Poor (<50)'),
        ('not_scored', 'Not Scored'),
    ], compute="_compute_ai_score_range", string="Score Rating", store=True)

    resume_text = fields.Text(readonly=True)
    ai_score_breakdown = fields.Html(readonly=True, string="Score Breakdown")

    # Detailed matching fields
    matched_skills = fields.Text(readonly=True, string="Matched Skills")
    missing_skills = fields.Text(readonly=True, string="Missing Skills")
    matched_keywords = fields.Text(readonly=True, string="Matched Keywords")
    extracted_experience_years = fields.Float(readonly=True, string="Experience (Years)")


    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)

        for applicant, vals in zip(applicants, vals_list):
            # Auto-score ONLY if resume is provided at creation
            if vals.get('resume'):
                try:
                    applicant._auto_score_resume_safe()
                    # Send acknowledgement email
                    applicant._send_resume_acknowledgement_email()
                except Exception as e:
                    _logger.error(
                        "Auto resume scoring failed for applicant %s: %s",
                        applicant.id, str(e)
                    )

        return applicants

    def write(self, vals):
        res = super().write(vals)

        # Resume uploaded or replaced
        if 'resume' in vals:
            for applicant in self:
                if applicant.resume:
                    try:
                        applicant._auto_score_resume_safe()
                        # Send acknowledgement email (only if not sent before)
                        applicant._send_resume_acknowledgement_email()
                    except Exception as e:
                        _logger.error(
                            "Auto resume scoring failed for applicant %s: %s",
                            applicant.id, str(e)
                        )

        return res

    def _send_resume_acknowledgement_email(self):
        """Send acknowledgement email when resume is received"""
        self.ensure_one()
        try:
            template = self.env.ref('instix_customisations.email_template_stage1_resume_acknowledgement')
            if template:
                template.send_mail(self.id, force_send=True)
                _logger.info(
                    "Resume acknowledgement email sent to %s for applicant %s",
                    self.email_from, self.id
                )
        except Exception as e:
            _logger.error(
                "Failed to send resume acknowledgement email for applicant %s: %s",
                self.id, str(e)
            )
    def _auto_score_resume_safe(self):
        """
        Safely auto-score resume:
        - no UserError
        - no infinite loop
        - no re-scoring if already scored
        """
        self.ensure_one()

        # Do not rescore if already scored
        if self.ai_score and self.resume_text:
            return

        if not self.resume:
            return

        try:
            self.action_score_resume()
        except UserError as e:
            # Do NOT block applicant creation
            _logger.warning(
                "Resume scoring skipped for applicant %s: %s",
                self.id, e.name if hasattr(e, 'name') else str(e)
            )


    @api.depends('ai_score')
    def _compute_ai_score_range(self):
        """Compute score range based on AI score"""
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

    def action_score_resume(self):
        """Main action to score resume"""
        for applicant in self:
            if not applicant.resume:
                raise UserError("Please upload a resume first.")

            # Extract text from resume
            resume_text = applicant._extract_resume_text()

            # Calculate comprehensive score
            score_data = applicant._calculate_comprehensive_score(resume_text)

            # Update applicant record
            applicant.write({
                'resume_text': resume_text,
                'ai_score': score_data['total_score'],
                'ai_score_breakdown': score_data['breakdown_html'],
                'matched_skills': score_data['matched_skills'],
                'missing_skills': score_data['missing_skills'],
                'matched_keywords': score_data['matched_keywords'],
                'extracted_experience_years': score_data['experience_years'],
            })

            # Auto-move to qualified stage if score is sufficient
            applicant._auto_move_to_qualified_stage()

    def _extract_resume_text(self):
        """Extract and clean text from PDF resume"""
        self.ensure_one()
        try:
            resume_bytes = base64.b64decode(self.resume)
            with pdfplumber.open(BytesIO(resume_bytes)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)

            if not text.strip():
                raise UserError("No readable text found in the resume.")

            # Clean text: remove null bytes and control characters
            text = text.replace('\x00', '')
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

            return text.strip()

        except Exception as e:
            _logger.error("Resume parsing failed: %s", str(e))
            raise UserError(f"Unable to extract text from the resume: {str(e)}")

    def _calculate_comprehensive_score(self, resume_text):
        """
        Enhanced scoring algorithm with configurable weights
        Returns: dict with total_score, breakdown_html, and match details
        """
        self.ensure_one()
        resume_lower = resume_text.lower()

        # Initialize scoring components
        scores = {}
        max_scores = {
            'skills': 40,
            'keywords': 25,
            'experience': 20,
            'structure': 10,
            'education': 5
        }

        # 1. SKILLS MATCHING (40 points max)
        skill_result = self._score_skills_match(resume_lower)
        scores['skills'] = skill_result['score']
        matched_skills = skill_result['matched']
        missing_skills = skill_result['missing']

        # 2. KEYWORDS MATCHING (25 points max)
        keyword_result = self._score_keywords_match(resume_lower)
        scores['keywords'] = keyword_result['score']
        matched_keywords = keyword_result['matched']

        # 3. EXPERIENCE MATCHING (20 points max)
        experience_result = self._score_experience_match(resume_text)
        scores['experience'] = experience_result['score']
        experience_years = experience_result['years']

        # 4. RESUME STRUCTURE (10 points max)
        scores['structure'] = self._score_resume_structure(resume_lower)

        # 5. EDUCATION/CERTIFICATIONS (5 points max)
        scores['education'] = self._score_education(resume_lower)

        # Calculate total score
        total_score = sum(scores.values())
        total_score = min(round(total_score, 2), 100)

        # Generate HTML breakdown
        breakdown_html = self._generate_score_breakdown_html(
            scores, max_scores, total_score,
            skill_result, keyword_result, experience_result
        )

        return {
            'total_score': total_score,
            'breakdown_html': breakdown_html,
            'matched_skills': ', '.join(matched_skills) if matched_skills else 'None',
            'missing_skills': ', '.join(missing_skills) if missing_skills else 'None',
            'matched_keywords': ', '.join(matched_keywords) if matched_keywords else 'None',
            'experience_years': experience_years,
        }

    def _score_skills_match(self, resume_lower):
        """Score based on required skills match"""
        if not self.job_id.resume_skill_ids:
            return {'score': 30, 'matched': [], 'missing': [], 'match_rate': 0}

        required_skills = [skill.name.lower().strip() for skill in self.job_id.resume_skill_ids]
        matched_skills = []
        missing_skills = []

        for skill in required_skills:
            # Use fuzzy matching for better results
            if self._fuzzy_search(skill, resume_lower):
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        total_skills = len(required_skills)
        matched_count = len(matched_skills)
        match_rate = matched_count / total_skills if total_skills > 0 else 0

        # Progressive scoring based on match percentage
        if match_rate >= 0.95:
            score = 40
        elif match_rate >= 0.85:
            score = 38
        elif match_rate >= 0.75:
            score = 35
        elif match_rate >= 0.65:
            score = 32
        elif match_rate >= 0.50:
            score = 28
        elif match_rate >= 0.40:
            score = 24
        elif match_rate >= 0.30:
            score = 20
        elif match_rate >= 0.20:
            score = 15
        elif match_rate >= 0.10:
            score = 10
        else:
            score = 5

        return {
            'score': score,
            'matched': matched_skills,
            'missing': missing_skills,
            'match_rate': match_rate
        }

    def _score_keywords_match(self, resume_lower):
        """Score based on keyword presence"""
        if not self.job_id.resume_keyword_ids:
            return {'score': 18, 'matched': [], 'match_rate': 0}

        required_keywords = [kw.name.lower().strip() for kw in self.job_id.resume_keyword_ids]
        matched_keywords = []

        for keyword in required_keywords:
            if self._fuzzy_search(keyword, resume_lower):
                matched_keywords.append(keyword)

        total_keywords = len(required_keywords)
        matched_count = len(matched_keywords)
        match_rate = matched_count / total_keywords if total_keywords > 0 else 0

        # Progressive scoring
        if match_rate >= 0.90:
            score = 25
        elif match_rate >= 0.75:
            score = 22
        elif match_rate >= 0.60:
            score = 19
        elif match_rate >= 0.45:
            score = 16
        elif match_rate >= 0.30:
            score = 13
        elif match_rate >= 0.20:
            score = 10
        else:
            score = max(5, int(match_rate * 25))

        return {
            'score': score,
            'matched': matched_keywords,
            'match_rate': match_rate
        }

    def _score_experience_match(self, resume_text):
        """Score based on years of experience"""
        years = self._extract_years_experience(resume_text)
        min_exp = self.job_id.resume_min_experience or 0
        max_exp = self.job_id.resume_max_experience or 999

        if min_exp == 0 and max_exp == 999:
            # No experience requirements set
            return {'score': 15, 'years': years, 'status': 'No requirements set'}

        if years < min_exp:
            # Under-qualified
            gap = min_exp - years
            if gap <= 1:
                score = 15
                status = f"Slightly below minimum ({years} vs {min_exp} required)"
            elif gap <= 2:
                score = 12
                status = f"Below minimum ({years} vs {min_exp} required)"
            else:
                score = max(5, 20 - gap * 2)
                status = f"Significantly below minimum ({years} vs {min_exp} required)"
        elif years > max_exp:
            # Over-qualified (still acceptable)
            over = years - max_exp
            if over <= 2:
                score = 18
                status = f"Slightly over maximum ({years} vs {max_exp} preferred)"
            else:
                score = 16
                status = f"Over-qualified ({years} vs {max_exp} preferred)"
        else:
            # Perfect fit
            score = 20
            status = f"Perfect match ({years} years, {min_exp}-{max_exp} required)"

        return {
            'score': score,
            'years': years,
            'status': status
        }

    def _score_resume_structure(self, resume_lower):
        """Score based on resume structure and ATS compatibility"""
        key_sections = [
            'experience', 'work history', 'employment',
            'education', 'qualification',
            'skills', 'competencies', 'expertise',
            'summary', 'objective', 'profile',
            'projects', 'achievements',
            'certification', 'training'
        ]

        found_sections = sum(1 for section in key_sections if section in resume_lower)

        # Look for contact information
        has_email = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resume_lower))
        has_phone = bool(re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', resume_lower))

        # Scoring
        structure_score = min(found_sections * 1.2, 8)
        if has_email:
            structure_score += 1
        if has_phone:
            structure_score += 1

        return min(round(structure_score, 2), 10)

    def _score_education(self, resume_lower):
        """Score based on education level"""
        education_keywords = {
            'phd': 5, 'doctorate': 5,
            'master': 4, 'mba': 4, 'ms': 4, 'ma': 4,
            'bachelor': 3, 'degree': 3, 'bs': 3, 'ba': 3,
            'diploma': 2, 'certificate': 1
        }

        max_edu_score = 0
        for keyword, points in education_keywords.items():
            if keyword in resume_lower:
                max_edu_score = max(max_edu_score, points)

        return max_edu_score

    def _extract_years_experience(self, text):
        """Extract years of experience from resume text"""
        years = 0

        # Pattern 1: "X years of experience" or "X+ years of experience"
        pattern1 = re.search(r'(\d+)\+?\s*years?\s+(?:of\s+)?experience', text, re.IGNORECASE)
        if pattern1:
            years = float(pattern1.group(1))
            _logger.info(f"Experience found via pattern 'X years of experience': {years}")
            return years

        # Pattern 2: "X+ years in..." or "X years as..."
        pattern2 = re.search(r'(\d+)\+?\s*years?\s+(?:in|as|with)', text, re.IGNORECASE)
        if pattern2:
            years = float(pattern2.group(1))
            _logger.info(f"Experience found via pattern 'X years in/as': {years}")
            return years

        # Pattern 3: Calculate from work history dates (only if no explicit experience mentioned)
        # Look for date ranges like "2020 - 2024" or "2020 - Present"
        date_ranges = re.findall(
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(20\d{2}|19\d{2})\s*[-–—to]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(20\d{2}|19\d{2}|present|current)',
            text,
            re.IGNORECASE
        )

        if date_ranges:
            current_year = 2026
            unique_ranges = []

            for month1, start, month2, end in date_ranges:
                start_year = int(start)
                end_year = current_year if end.lower() in ['present', 'current'] else int(end)

                # Skip invalid ranges
                if end_year < start_year:
                    continue

                # Avoid double-counting overlapping periods
                duration = end_year - start_year
                unique_ranges.append({
                    'start': start_year,
                    'end': end_year,
                    'duration': duration
                })

            # Sort by start year and merge overlapping periods
            if unique_ranges:
                unique_ranges.sort(key=lambda x: x['start'])
                merged_years = 0
                last_end = 0

                for period in unique_ranges:
                    if period['start'] > last_end:
                        # Non-overlapping period
                        merged_years += period['duration']
                        last_end = period['end']
                    elif period['end'] > last_end:
                        # Partial overlap - add only the non-overlapping part
                        merged_years += (period['end'] - last_end)
                        last_end = period['end']

                years = min(merged_years, 50)  # Cap at 50 years
                _logger.info(
                    f"Experience calculated from date ranges: {years} years ({len(unique_ranges)} periods found)")
                return years

        _logger.info("No experience information found in resume")
        return 0

    def _fuzzy_search(self, keyword, text, threshold=0.85):
        """
        Fuzzy search for keyword in text
        Returns True if keyword found with similarity >= threshold
        """
        keyword = keyword.lower().strip()

        # Exact match
        if keyword in text:
            return True

        # Split keyword into words for multi-word matching
        keyword_words = keyword.split()

        # For single-word keywords, use fuzzy matching
        if len(keyword_words) == 1:
            words = re.findall(r'\b\w+\b', text.lower())
            for word in words:
                similarity = SequenceMatcher(None, keyword, word).ratio()
                if similarity >= threshold:
                    return True
        else:
            # For multi-word keywords, check if all words present
            if all(word in text for word in keyword_words):
                return True

        return False

    def _generate_score_breakdown_html(self, scores, max_scores, total_score,
                                       skill_result, keyword_result, experience_result):
        """Generate HTML breakdown of scoring"""

        # Determine color and rating based on score
        if total_score >= 90:
            color = '#10b981'  # Emerald green
            bg_color = '#d1fae5'
            rating = 'Excellent'
            icon = '🌟'
        elif total_score >= 80:
            color = '#22c55e'  # Green
            bg_color = '#dcfce7'
            rating = 'Great'
            icon = '✅'
        elif total_score >= 70:
            color = '#84cc16'  # Lime
            bg_color = '#ecfccb'
            rating = 'Good'
            icon = '👍'
        elif total_score >= 50:
            color = '#f59e0b'  # Amber
            bg_color = '#fef3c7'
            rating = 'Fair'
            icon = '⚠️'
        else:
            color = '#ef4444'  # Red
            bg_color = '#fee2e2'
            rating = 'Poor'
            icon = '❌'

        # Calculate percentage for each category
        def get_percentage(score, max_score):
            return int((score / max_score * 100)) if max_score > 0 else 0

        def get_bar_color(percentage):
            if percentage >= 90:
                return '#10b981'
            elif percentage >= 75:
                return '#22c55e'
            elif percentage >= 60:
                return '#84cc16'
            elif percentage >= 40:
                return '#f59e0b'
            else:
                return '#ef4444'

        html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

            <!-- Header Section -->
            <div style="background: {bg_color}; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid {color};">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <h2 style="margin: 0; color: {color}; font-size: 28px;">{icon} {rating}</h2>
                        <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">Resume Score Analysis</p>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 48px; font-weight: bold; color: {color}; line-height: 1;">{total_score}</div>
                        <div style="color: #9ca3af; font-size: 14px;">out of 100</div>
                    </div>
                </div>
            </div>

            <!-- Score Breakdown Table -->
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; background: white;">
                <thead>
                    <tr style="background: #f9fafb; border-bottom: 2px solid #e5e7eb;">
                        <th style="padding: 12px; text-align: left; font-weight: 600; color: #374151; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Category</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600; color: #374151; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Score</th>
                        <th style="padding: 12px; text-align: left; font-weight: 600; color: #374151; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; width: 45%;">Performance</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Skills Match -->
                    <tr style="border-bottom: 1px solid #f3f4f6;">
                        <td style="padding: 14px; color: #1f2937; font-weight: 500;">
                            <div style="display: flex; align-items: center;">
                                <span style="margin-right: 8px; font-size: 18px;">🎯</span>
                                Skills Match
                            </div>
                        </td>
                        <td style="padding: 14px; text-align: center;">
                            <span style="font-size: 18px; font-weight: bold; color: {get_bar_color(get_percentage(scores['skills'], max_scores['skills']))};">
                                {scores['skills']}/{max_scores['skills']}
                            </span>
                        </td>
                        <td style="padding: 14px;">
                            <div style="background: #e5e7eb; border-radius: 10px; height: 8px; margin-bottom: 5px; overflow: hidden;">
                                <div style="background: {get_bar_color(get_percentage(scores['skills'], max_scores['skills']))}; height: 100%; width: {get_percentage(scores['skills'], max_scores['skills'])}%; border-radius: 10px; transition: width 0.3s;"></div>
                            </div>
                            <div style="color: #6b7280; font-size: 12px;">
                                {len(skill_result['matched'])}/{len(skill_result['matched']) + len(skill_result['missing'])} skills matched ({int(skill_result['match_rate'] * 100)}%)
                            </div>
                        </td>
                    </tr>

                    <!-- Keywords Match -->
                    <tr style="border-bottom: 1px solid #f3f4f6; background: #fafafa;">
                        <td style="padding: 14px; color: #1f2937; font-weight: 500;">
                            <div style="display: flex; align-items: center;">
                                <span style="margin-right: 8px; font-size: 18px;">🔑</span>
                                Keywords Match
                            </div>
                        </td>
                        <td style="padding: 14px; text-align: center;">
                            <span style="font-size: 18px; font-weight: bold; color: {get_bar_color(get_percentage(scores['keywords'], max_scores['keywords']))};">
                                {scores['keywords']}/{max_scores['keywords']}
                            </span>
                        </td>
                        <td style="padding: 14px;">
                            <div style="background: #e5e7eb; border-radius: 10px; height: 8px; margin-bottom: 5px; overflow: hidden;">
                                <div style="background: {get_bar_color(get_percentage(scores['keywords'], max_scores['keywords']))}; height: 100%; width: {get_percentage(scores['keywords'], max_scores['keywords'])}%; border-radius: 10px;"></div>
                            </div>
                            <div style="color: #6b7280; font-size: 12px;">
                                {len(keyword_result['matched'])} keywords found ({int(keyword_result['match_rate'] * 100)}%)
                            </div>
                        </td>
                    </tr>

                    <!-- Experience -->
                    <tr style="border-bottom: 1px solid #f3f4f6;">
                        <td style="padding: 14px; color: #1f2937; font-weight: 500;">
                            <div style="display: flex; align-items: center;">
                                <span style="margin-right: 8px; font-size: 18px;">💼</span>
                                Experience Fit
                            </div>
                        </td>
                        <td style="padding: 14px; text-align: center;">
                            <span style="font-size: 18px; font-weight: bold; color: {get_bar_color(get_percentage(scores['experience'], max_scores['experience']))};">
                                {scores['experience']}/{max_scores['experience']}
                            </span>
                        </td>
                        <td style="padding: 14px;">
                            <div style="background: #e5e7eb; border-radius: 10px; height: 8px; margin-bottom: 5px; overflow: hidden;">
                                <div style="background: {get_bar_color(get_percentage(scores['experience'], max_scores['experience']))}; height: 100%; width: {get_percentage(scores['experience'], max_scores['experience'])}%; border-radius: 10px;"></div>
                            </div>
                            <div style="color: #6b7280; font-size: 12px;">
                                {experience_result['status']}
                            </div>
                        </td>
                    </tr>

                    <!-- Resume Structure -->
                    <tr style="border-bottom: 1px solid #f3f4f6; background: #fafafa;">
                        <td style="padding: 14px; color: #1f2937; font-weight: 500;">
                            <div style="display: flex; align-items: center;">
                                <span style="margin-right: 8px; font-size: 18px;">📄</span>
                                Resume Structure
                            </div>
                        </td>
                        <td style="padding: 14px; text-align: center;">
                            <span style="font-size: 18px; font-weight: bold; color: {get_bar_color(get_percentage(scores['structure'], max_scores['structure']))};">
                                {scores['structure']}/{max_scores['structure']}
                            </span>
                        </td>
                        <td style="padding: 14px;">
                            <div style="background: #e5e7eb; border-radius: 10px; height: 8px; margin-bottom: 5px; overflow: hidden;">
                                <div style="background: {get_bar_color(get_percentage(scores['structure'], max_scores['structure']))}; height: 100%; width: {get_percentage(scores['structure'], max_scores['structure'])}%; border-radius: 10px;"></div>
                            </div>
                            <div style="color: #6b7280; font-size: 12px;">
                                ATS-friendly format assessment
                            </div>
                        </td>
                    </tr>

                    <!-- Education -->
                    <tr>
                        <td style="padding: 14px; color: #1f2937; font-weight: 500;">
                            <div style="display: flex; align-items: center;">
                                <span style="margin-right: 8px; font-size: 18px;">🎓</span>
                                Education Level
                            </div>
                        </td>
                        <td style="padding: 14px; text-align: center;">
                            <span style="font-size: 18px; font-weight: bold; color: {get_bar_color(get_percentage(scores['education'], max_scores['education']))};">
                                {scores['education']}/{max_scores['education']}
                            </span>
                        </td>
                        <td style="padding: 14px;">
                            <div style="background: #e5e7eb; border-radius: 10px; height: 8px; margin-bottom: 5px; overflow: hidden;">
                                <div style="background: {get_bar_color(get_percentage(scores['education'], max_scores['education']))}; height: 100%; width: {get_percentage(scores['education'], max_scores['education'])}%; border-radius: 10px;"></div>
                            </div>
                            <div style="color: #6b7280; font-size: 12px;">
                                Qualification level detected
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>

            <!-- Recommendation Box -->
            <div style="background: {bg_color}; padding: 16px; border-radius: 8px; border-left: 4px solid {color}; margin-top: 20px;">
                <div style="display: flex; align-items: center;">
                    <span style="font-size: 24px; margin-right: 12px;">{icon}</span>
                    <div>
                        <div style="font-weight: 600; color: {color}; font-size: 15px; margin-bottom: 3px;">
                            {'✅ RECOMMENDED - Strong candidate for next stage' if total_score >= 70
        else '⚠️ REVIEW REQUIRED - Needs careful evaluation' if total_score >= 50
        else '❌ NOT RECOMMENDED - Does not meet minimum requirements'}
                        </div>
                        <div style="color: #6b7280; font-size: 13px;">
                            {'This candidate shows excellent alignment with job requirements.' if total_score >= 70
        else 'This candidate shows partial alignment. Additional screening recommended.' if total_score >= 50
        else 'This candidate does not meet the minimum threshold for this position.'}
                        </div>
                    </div>
                </div>
            </div>

        </div>
        """

        return html

    def _auto_move_to_qualified_stage(self):
        """Auto-move applicant to qualified stage if score meets threshold"""
        self.ensure_one()

        if not self.job_id or not self.ai_score:
            return

        required_score = self.job_id.resume_pass_score or 70.0
        if self.ai_score < required_score:
            failed_stage = self.env['hr.recruitment.stage'].search([
                ('name', '=', 'Dropped'),
                '|',
                ('job_ids', 'in', self.job_id.id),
                ('job_ids', '=', False)
            ], limit=1)

            if failed_stage:
                self.write({'stage_id': failed_stage.id})
                applicant.action_send_level_2_failed_email(failure_type='resume')
            _logger.info(f"Applicant {self.partner_name} score {self.ai_score} below threshold {required_score}")
            return

        stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Qualified Resume'),
            '|',
            ('job_ids', 'in', self.job_id.id),
            ('job_ids', '=', False)
        ], limit=1)

        if stage and self.stage_id != stage:
            _logger.info(f"Moving applicant {self.partner_name} to Qualified Resume stage")
            self.stage_id = stage.id

    def action_send_video_survey(self):
        self.ensure_one()

        # 1️⃣ Ensure partner exists
        if not self.partner_id:
            if not self.partner_name:
                raise UserError(_('Please provide an applicant name.'))

            self.partner_id = self.env['res.partner'].sudo().create({
                'is_company': False,
                'name': self.partner_name,
                'email': self.email_from,
                'phone': self.partner_phone,
            })

        # 2️⃣ Validate survey
        if not self.job_id or not self.job_id.three_minute_video_survey_id:
            raise UserError(_('No 3-Minute Video Survey configured for this job.'))

        survey = self.job_id.three_minute_video_survey_id
        survey.check_validity()

        # 3️⃣ Email template
        template = self.env.ref(
            'instix_customisations.email_three_minute_video_survey',
            raise_if_not_found=False
        )

        # 4️⃣ Create invite
        invite = self.env['survey.invite'].create({
            'survey_id': survey.id,
            'partner_ids': [(6, 0, self.partner_id.ids)],
            'applicant_id': self.id,
            'template_id': template.id if template else False,
            'deadline': fields.Datetime.now() + timedelta(days=7),
        })

        invite.with_user(self.user_id).action_invite()
        next_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', '3 Minute Video Posting'),
            '|',
            ('job_ids', 'in', self.job_id.id),
            ('job_ids', '=', False)
        ], limit=1)

        if next_stage:
            self.with_user(self.user_id).write({
                'stage_id': next_stage.id
            })
        else:
            _logger.warning(
                "Stage '3 Minute Video Posting' not found for applicant %s",
                self.id
            )

        return True

    def action_send_analytical_skills_survey(self):
        self.ensure_one()
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
        invite.with_user(self.user_id).action_invite()

        return True
    


    def action_send_logical_skills_survey(self):
        self.ensure_one()
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
        invite.with_user(self.user_id).action_invite()

        return True
    


    def action_send_gems_stone_survey(self):
        self.ensure_one()
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
        invite.with_user(self.user_id).action_invite()

        return True

    from odoo import models, fields, api
    import logging

    _logger = logging.getLogger(__name__)

    class HrApplicant(models.Model):
        _inherit = 'hr.applicant'

        # Existing fields...

        def action_send_level_2_failed_email(self, failure_type='assessment'):
            """
            Send failure email based on type

            :param failure_type: 'assessment' for test failures, 'resume' for resume rejection
            """
            self.ensure_one()

            # Determine which template to use
            if failure_type == 'resume':
                template_xml_id = 'instix_customisations.email_template_resume_rejected'
            else:  # default to assessment
                template_xml_id = 'instix_customisations.email_level_2_failed'

            # Get the template
            template = self.env.ref(template_xml_id, raise_if_not_found=False)

            if template:
                template.with_user(self.user_id).send_mail(
                    self.id,
                    force_send=True,  # Send immediately
                )
                _logger.info(
                    "%s failure email sent to %s for applicant %s",
                    failure_type.capitalize(), self.email_from, self.id
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

    def action_open_all_surveys(self):
        self.ensure_one()

        if not self.job_id or not self.job_id.three_minute_video_survey_id:
            raise UserError(_("No 3-Minute Video Survey configured for this job."))

        return {
            'name': _('Applicant Surveys'),
            'type': 'ir.actions.act_window',
            'res_model': 'survey.user_input',
            'view_mode': 'list,form',
            'domain': [
                ('applicant_id', '=', self.id),
            ],
            'context': {
                'default_applicant_id': self.id,
                'search_default_group_by_survey': 1,

            },
        }
class HRSkill(models.Model):
    _name = 'resume.skill'
    _description = 'HR Skill'

    name = fields.Char(required=True)
