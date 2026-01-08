from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import email_normalize
from datetime import datetime, timedelta
import base64
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from io import BytesIO
import pdfplumber
import logging
import pickle
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from lxml import etree
from odoo.tools.convert import convert_file

nltk.download('stopwords')
nltk.download('wordnet')

_logger = logging.getLogger(__name__)


class AIResumeScreening(models.Model):
    _name = 'ai.resume.screening'
    _description = 'AI Resume Screening'

    name = fields.Char(string='Screening Name', required=True)
    job_position_id = fields.Many2one('hr.job', string='Job Position', required=True)
    keyword_ids = fields.Many2many('ai.resume.keyword', string='Keywords')
    min_years_experience = fields.Integer(string='Minimum Years of Experience', default=1)
    applicant_ids = fields.One2many('hr.applicant', 'ai_screening_id',
                                    string='Applicants')
    model_trained = fields.Boolean(string='AI Model Trained', default=False)
    model_data = fields.Binary(string='AI Model Data', attachment=True)
    
    # Scoring Weight Configuration
    keyword_score_weight = fields.Float(string='Keyword Score Weight (%)', default=40.0,
                                        help='Percentage weight for keyword matching in total score (0-100)')
    experience_score_weight = fields.Float(string='Experience Score Weight (%)', default=20.0,
                                          help='Percentage weight for years of experience in total score (0-100)')
    structure_score_weight = fields.Float(string='Structure Score Weight (%)', default=10.0,
                                         help='Percentage weight for resume structure quality in total score (0-100)')
    ai_prediction_weight = fields.Float(string='AI Prediction Weight (%)', default=30.0,
                                      help='Percentage weight for AI/ML prediction in total score (0-100)')
    total_weight = fields.Float(string='Total Weight (%)', compute='_compute_total_weight', store=False,
                               help='Sum of all score weights (should be 100%)')
    
    # Automation Settings
    auto_screen_enabled = fields.Boolean(string='Auto-Screen New Applicants', default=True,
                                         help='Automatically score resumes when new applicants are added')
    auto_train_enabled = fields.Boolean(string='Auto-Retrain Model', default=False,
                                        help='Automatically retrain model when enough new scored data is available')
    auto_train_threshold = fields.Integer(string='New Data Threshold for Retraining', default=10,
                                          help='Number of new scored applicants needed to trigger retraining')
    email_notification_enabled = fields.Boolean(string='Email Notifications', default=False,
                                                help='Send email notifications for high-scoring candidates')
    summary_notification_frequency = fields.Selection([
        ('none', 'Disabled'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ], string='Summary Notification Frequency', default='none',
        help='Frequency of summary email notifications with approved candidates')
    max_candidates_in_email = fields.Integer(string='Max Candidates per Email', default=50,
                                             help='Maximum number of candidates to include in summary email (sorted by score)')
    high_score_threshold = fields.Float(string='High Score Threshold', default=80.0,
                                         help='Minimum score to trigger email notification')
    notification_recipient_ids = fields.Many2many('res.users', string='Notification Recipients',
                                                   help='Users who will receive email notifications')
    last_auto_screen_date = fields.Datetime(string='Last Auto-Screen Date', readonly=True)
    last_auto_train_date = fields.Datetime(string='Last Auto-Train Date', readonly=True)
    last_summary_notification_date = fields.Datetime(string='Last Summary Notification Date', readonly=True)
    
    # Computed fields for kanban view
    applicant_count = fields.Integer(string='Applicants Count', compute='_compute_applicant_stats', store=False)
    high_score_count = fields.Integer(string='High Score Count', compute='_compute_applicant_stats', store=False)
    avg_score = fields.Float(string='Average Score', compute='_compute_applicant_stats', store=False)
    
    @api.depends('keyword_score_weight', 'experience_score_weight', 'structure_score_weight', 'ai_prediction_weight')
    def _compute_total_weight(self):
        """Compute total weight percentage."""
        for record in self:
            record.total_weight = (record.keyword_score_weight + 
                                  record.experience_score_weight + 
                                  record.structure_score_weight + 
                                  record.ai_prediction_weight)
    
    @api.depends('applicant_ids', 'applicant_ids.ai_score')
    def _compute_applicant_stats(self):
        """Compute statistics for kanban view."""
        for record in self:
            applicants = record.applicant_ids.filtered(lambda a: a.ai_score > 0)
            record.applicant_count = len(record.applicant_ids)
            record.high_score_count = len(applicants.filtered(lambda a: a.ai_score >= 70))
            if applicants:
                record.avg_score = sum(applicants.mapped('ai_score')) / len(applicants)
            else:
                record.avg_score = 0.0

    @api.model
    def _prepare_training_data(self):
        """Prepare training data incrementally."""
        applicants = self.applicant_ids.filtered(
            lambda
                a: a.resume_text and a.ai_score is not None and a.resume_text != "Error: Unable to extract text from the resume."
        )
        if len(applicants) < 2:
            raise UserError(
                "Please add at least 5 valid scored applicants to train the model.")

        X = [applicant.resume_text for applicant in applicants]
        y = [1 if applicant.ai_score >= 70 else 0 for applicant in applicants]
        return X, y

    def train_model(self):
        """Train the AI model incrementally."""
        X, y = self._prepare_training_data()
        model = make_pipeline(TfidfVectorizer(stop_words=stopwords.words('english')),
                              MultinomialNB())
        model.fit(X, y)

        # Serialize and save the model
        self.model_data = base64.b64encode(pickle.dumps(model))
        self.model_trained = True
        _logger.info("AI model trained successfully for screening %s", self.name)

    def _get_model(self):
        """Load the trained model."""
        if not self.model_trained or not self.model_data:
            raise UserError(
                "The AI model has not been trained yet. Please train the model first.")
        return pickle.loads(base64.b64decode(self.model_data))

    def screen_resumes(self):
        """Screen resumes efficiently."""
        if not self.model_trained:
            raise UserError("Please train the AI model before screening resumes.")

        model = self._get_model()
        to_screen = self.applicant_ids.filtered(
            lambda a: a.resume_text and (not a.ai_score or a.ai_score == 0))
        for applicant in to_screen:
            applicant.ai_score = self._score_resume(applicant.resume_text, model)
        
        self.last_auto_screen_date = datetime.now()
        return len(to_screen)
    
    def auto_screen_new_applicants(self):
        """Automatically screen new applicants if model is trained."""
        if not self.model_trained or not self.auto_screen_enabled or not self.model_data:
            return
        
        try:
            model = self._get_model()
            to_screen = self.applicant_ids.filtered(
                lambda a: a.resume_text and 
                a.resume_text != "Error: Unable to extract text from the resume." and
                (not a.ai_score or a.ai_score == 0))
            
            if to_screen:
                for applicant in to_screen:
                    applicant.ai_score = self._score_resume(applicant.resume_text, model)
                    # Update applicant status based on score
                    applicant._update_status_from_score()
                    # Send notification if enabled
                    if self.email_notification_enabled and applicant.ai_score >= self.high_score_threshold:
                        applicant._send_high_score_notification()
                
                # Note: We don't update last_auto_screen_date here to avoid serialization conflicts
                # when multiple cron jobs run simultaneously. The timestamp is non-critical.
                # The important part (screening applicants) is already completed successfully.
                # If you need the timestamp, it can be updated separately in a background job
                # or when viewing the screening record.
                
                _logger.info("Auto-screened %d applicants for screening %s", len(to_screen), self.name)
        except Exception as e:
            # Handle other errors in the screening process
            error_msg = str(e).lower()
            if 'serialize' in error_msg or 'concurrent' in error_msg or 'could not serialize' in error_msg:
                _logger.warning("Concurrent update detected for screening %s (ID: %s): %s", 
                              self.name, self.id, str(e))
            else:
                _logger.error("Error in auto-screening for screening %s: %s", self.name, str(e))
    
    def check_and_auto_train(self):
        """Check if enough new data is available and auto-train if enabled."""
        if not self.auto_train_enabled:
            return
        
        # Count newly scored applicants since last training
        if self.last_auto_train_date:
            new_applicants = self.applicant_ids.filtered(
                lambda a: a.write_date > self.last_auto_train_date and 
                a.ai_score > 0 and 
                a.resume_text and 
                a.resume_text != "Error: Unable to extract text from the resume.")
        else:
            new_applicants = self.applicant_ids.filtered(
                lambda a: a.ai_score > 0 and 
                a.resume_text and 
                a.resume_text != "Error: Unable to extract text from the resume.")
        
        if len(new_applicants) >= self.auto_train_threshold:
            try:
                self.train_model()
                self.last_auto_train_date = datetime.now()
                _logger.info("Auto-retrained model for screening %s with %d new applicants", 
                           self.name, len(new_applicants))
            except Exception as e:
                _logger.error("Error in auto-training: %s", str(e))
    
    @api.model
    def cron_auto_screen_all(self):
        """Cron job to automatically screen all active screenings."""
        active_screenings = self.search([('auto_screen_enabled', '=', True), ('model_trained', '=', True)])
        for screening in active_screenings:
            try:
                screening.auto_screen_new_applicants()
            except Exception as e:
                # Log but don't fail the entire cron job if one screening fails
                _logger.error("Error in cron auto-screening for screening %s: %s", screening.name, str(e))
                continue
    
    @api.model
    def cron_auto_train_all(self):
        """Cron job to automatically retrain models when enough data is available."""
        active_screenings = self.search([('auto_train_enabled', '=', True)])
        for screening in active_screenings:
            screening.check_and_auto_train()
    
    @api.model
    def cron_daily_notifications(self):
        """Cron job to send daily summary notifications with approved candidates."""
        active_screenings = self.search([('summary_notification_frequency', '=', 'daily')])
        for screening in active_screenings:
            screening.send_summary_notification()
    
    @api.model
    def cron_weekly_notifications(self):
        """Cron job to send weekly summary notifications with approved candidates."""
        active_screenings = self.search([('summary_notification_frequency', '=', 'weekly')])
        for screening in active_screenings:
            screening.send_summary_notification()
    
    @api.model
    def cron_monthly_notifications(self):
        """Cron job to send monthly summary notifications with approved candidates."""
        active_screenings = self.search([('summary_notification_frequency', '=', 'monthly')])
        for screening in active_screenings:
            screening.send_summary_notification()
    
    def action_view_top_matches(self):
        """Return action to view top matching applicants filtered by score threshold."""
        self.ensure_one()
        return {
            'name': f'Top Resume Matches - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.applicant',
            'view_mode': 'list',
            'domain': [
                ('ai_screening_id', '=', self.id),
                ('ai_score', '>=', self.high_score_threshold),
                ('ai_score', '>', 0)
            ],
            'context': {
                'default_ai_screening_id': self.id,
                'search_default_group_by_ai_score': 1,
            },
            'limit': 80,  # Show more records per page
        }
    
    def send_summary_notification(self):
        """Send summary email notification with list of approved/high-scoring candidates."""
        if not self.summary_notification_frequency or self.summary_notification_frequency == 'none':
            return
        if not self.notification_recipient_ids:
            return
        
        try:
            # Determine date range based on frequency and last notification date
            now = datetime.now()
            if self.last_summary_notification_date:
                if self.summary_notification_frequency == 'daily':
                    date_start = self.last_summary_notification_date
                elif self.summary_notification_frequency == 'weekly':
                    date_start = self.last_summary_notification_date - timedelta(days=7)
                elif self.summary_notification_frequency == 'monthly':
                    date_start = self.last_summary_notification_date - timedelta(days=30)
                else:
                    date_start = self.last_summary_notification_date
                date_filter = [('write_date', '>=', date_start)]
            else:
                # First time - get candidates from last period based on frequency
                if self.summary_notification_frequency == 'daily':
                    date_filter = [('write_date', '>=', now - timedelta(days=1))]
                elif self.summary_notification_frequency == 'weekly':
                    date_filter = [('write_date', '>=', now - timedelta(days=7))]
                elif self.summary_notification_frequency == 'monthly':
                    date_filter = [('write_date', '>=', now - timedelta(days=30))]
                else:
                    date_filter = []
            
            # Get high-scoring candidates
            high_scoring_applicants = self.applicant_ids.filtered(
                lambda a: a.ai_score >= self.high_score_threshold and
                a.resume_text and
                a.resume_text != "Error: Unable to extract text from the resume."
            ).filtered_domain(date_filter)
            
            if not high_scoring_applicants:
                return
            
            # Sort by score descending and limit to max_candidates_in_email
            high_scoring_applicants = high_scoring_applicants.sorted('ai_score', reverse=True)
            total_found = len(high_scoring_applicants)
            high_scoring_applicants = high_scoring_applicants[:self.max_candidates_in_email]
            
            # Get base URL for links
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
            
            # Frequency labels
            frequency_labels = {
                'daily': 'Daily',
                'weekly': 'Weekly',
                'monthly': 'Monthly'
            }
            frequency_label = frequency_labels.get(self.summary_notification_frequency, 'Summary')
            
            # Build email content
            period_text = f"{frequency_label} AI Resume Screening Summary"
            subject = f"{period_text} - {self.name} - {len(high_scoring_applicants)} Approved Candidate{'s' if len(high_scoring_applicants) != 1 else ''}"
            if total_found > len(high_scoring_applicants):
                subject += f" (Showing top {len(high_scoring_applicants)} of {total_found})"
            
            # Create advanced HTML table with candidate list
            candidates_table = """
            <div style="overflow-x: auto; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #5CA280 0%, #4a8a6a 100%); color: white;">
                            <th style="padding: 14px 16px; text-align: left; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">#</th>
                            <th style="padding: 14px 16px; text-align: left; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Candidate Name</th>
                            <th style="padding: 14px 16px; text-align: left; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Email</th>
                            <th style="padding: 14px 16px; text-align: left; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Position</th>
                            <th style="padding: 14px 16px; text-align: center; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">AI Score</th>
                            <th style="padding: 14px 16px; text-align: center; font-weight: 600; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for idx, applicant in enumerate(high_scoring_applicants, 1):
                row_color = '#ffffff' if idx % 2 == 0 else '#f8f9fa'
                # Score color coding
                if applicant.ai_score >= 90:
                    score_color = '#155724'
                    score_bg = '#d4edda'
                    score_badge = 'Excellent'
                elif applicant.ai_score >= 80:
                    score_color = '#28a745'
                    score_bg = '#d1ecf1'
                    score_badge = 'Great'
                elif applicant.ai_score >= 70:
                    score_color = '#856404'
                    score_bg = '#fff3cd'
                    score_badge = 'Good'
                else:
                    score_color = '#17a2b8'
                    score_bg = '#d1ecf1'
                    score_badge = 'Fair'
                
                candidates_table += f"""
                    <tr style="background-color: {row_color}; transition: background-color 0.2s;">
                        <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; color: #6c757d; font-weight: 600;">{idx}</td>
                        <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef;">
                            <div style="font-weight: 600; color: #2c3e50; font-size: 14px;">{applicant.name or 'N/A'}</div>
                            <div style="font-size: 11px; color: #6c757d; margin-top: 2px;">
                                <i class="fa fa-calendar" style="margin-right: 4px;"></i>
                                {applicant.create_date.strftime('%b %d, %Y') if applicant.create_date else 'N/A'}
                            </div>
                        </td>
                        <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef;">
                            <a href="mailto:{applicant.email_from or ''}" style="color: #5CA280; text-decoration: none; font-size: 13px;">
                                {applicant.email_from or 'N/A'}
                            </a>
                        </td>
                        <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; color: #495057; font-size: 13px;">
                            {applicant.job_id.name if applicant.job_id else 'N/A'}
                        </td>
                        <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center;">
                            <div style="display: inline-block; padding: 6px 12px; background-color: {score_bg}; color: {score_color}; border-radius: 20px; font-weight: 700; font-size: 14px; min-width: 70px;">
                                {applicant.ai_score:.1f}
                            </div>
                            <div style="font-size: 10px; color: #6c757d; margin-top: 4px;">{score_badge}</div>
                        </td>
                        <td style="padding: 12px 16px; border-bottom: 1px solid #e9ecef; text-align: center;">
                            <a href="{base_url}/web#id={applicant.id}&model=hr.applicant&view_type=form" 
                               style="background: linear-gradient(135deg, #5CA280 0%, #4a8a6a 100%); color: white; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 600; display: inline-block; box-shadow: 0 2px 4px rgba(92, 162, 128, 0.3); transition: transform 0.2s;">
                                <i class="fa fa-eye" style="margin-right: 4px;"></i>View
                            </a>
                        </td>
                    </tr>
                """
            
            candidates_table += """
                    </tbody>
                </table>
            </div>
            """
            
            # Calculate statistics
            total_applicants = len(self.applicant_ids)
            approved_count = len(self.applicant_ids.filtered(lambda a: a.ai_score >= self.high_score_threshold))
            avg_score = sum(self.applicant_ids.mapped('ai_score')) / len(self.applicant_ids) if self.applicant_ids else 0
            
            # Advanced email template design
            body_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f7fa;">
                <div style="max-width: 900px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                    <!-- Header with Gradient -->
                    <div style="background: linear-gradient(135deg, #5CA280 0%, #4a8a6a 100%); padding: 30px; text-align: center;">
                        <div style="display: inline-block; background-color: rgba(255,255,255,0.2); padding: 15px; border-radius: 50%; margin-bottom: 15px;">
                            <i class="fa fa-robot" style="font-size: 36px; color: white;"></i>
                        </div>
                        <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">
                            {period_text}
                        </h1>
                        <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 14px;">
                            <i class="fa fa-calendar" style="margin-right: 6px;"></i>
                            {now.strftime('%B %d, %Y at %I:%M %p')}
                        </p>
                    </div>
                    
                    <!-- Main Content -->
                    <div style="padding: 40px;">
                        <!-- Screening Info Card -->
                        <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #5CA280;">
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                                <div>
                                    <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">Screening Profile</div>
                                    <div style="font-size: 20px; font-weight: 700; color: #2c3e50; margin-bottom: 8px;">{self.name}</div>
                                    <div style="font-size: 14px; color: #495057;">
                                        <i class="fa fa-briefcase" style="margin-right: 6px; color: #5CA280;"></i>
                                        {self.job_position_id.name if self.job_position_id else 'N/A'}
                                    </div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;">Frequency</div>
                                    <div style="font-size: 18px; font-weight: 700; color: #5CA280;">{frequency_label}</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Summary Alert -->
                        <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #28a745;">
                            <div style="display: flex; align-items: center;">
                                <div style="background-color: #28a745; color: white; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 24px;">
                                    <i class="fa fa-check-circle"></i>
                                </div>
                                <div>
                                    <div style="font-size: 22px; font-weight: 700; color: #155724; margin-bottom: 5px;">
                                        {len(high_scoring_applicants)} Approved Candidate{'s' if len(high_scoring_applicants) != 1 else ''} Found
                                    </div>
                                    <div style="font-size: 13px; color: #2e7d32;">
                                        {'Showing top ' + str(len(high_scoring_applicants)) + ' of ' + str(total_found) + ' candidates' if total_found > len(high_scoring_applicants) else 'All approved candidates are listed below'}
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Candidates Table -->
                        {candidates_table}
                        
                        <!-- Statistics Cards -->
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 40px;">
                            <div style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); padding: 25px; border-radius: 8px; text-align: center; border-top: 3px solid #2196f3;">
                                <div style="font-size: 36px; font-weight: 700; color: #1976d2; margin-bottom: 8px;">{total_applicants}</div>
                                <div style="font-size: 13px; color: #1565c0; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Total Applicants</div>
                            </div>
                            <div style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); padding: 25px; border-radius: 8px; text-align: center; border-top: 3px solid #4caf50;">
                                <div style="font-size: 36px; font-weight: 700; color: #2e7d32; margin-bottom: 8px;">{approved_count}</div>
                                <div style="font-size: 13px; color: #1b5e20; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Approved (≥{self.high_score_threshold:.0f})</div>
                            </div>
                            <div style="background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); padding: 25px; border-radius: 8px; text-align: center; border-top: 3px solid #ff9800;">
                                <div style="font-size: 36px; font-weight: 700; color: #e65100; margin-bottom: 8px;">{avg_score:.1f}</div>
                                <div style="font-size: 13px; color: #bf360c; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Average Score</div>
                            </div>
                        </div>
                        
                        <!-- CTA Button -->
                        <div style="text-align: center; margin-top: 40px;">
                            <a href="{base_url}/web#id={self.id}&model=ai.resume.screening&view_type=form" 
                               style="background: linear-gradient(135deg, #5CA280 0%, #4a8a6a 100%); color: white; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600; display: inline-block; box-shadow: 0 4px 12px rgba(92, 162, 128, 0.4); transition: transform 0.2s;">
                                <i class="fa fa-eye" style="margin-right: 8px;"></i>View Full Screening Details
                            </a>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div style="background-color: #f8f9fa; padding: 25px; text-align: center; border-top: 1px solid #e9ecef;">
                        <p style="margin: 0; color: #6c757d; font-size: 12px; line-height: 1.6;">
                            This is an automated {frequency_label.lower()} summary from the AI Resume Screening system.<br>
                            <span style="color: #5CA280; font-weight: 600;">AI Resume Analyzer &amp; Screening for Odoo</span>
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Send email to all recipients
            email_to = ','.join([user.email for user in self.notification_recipient_ids if user.email])
            if email_to:
                mail_values = {
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': email_to,
                    'email_from': self.env.user.email or self.env.company.email,
                    'auto_delete': True,
                }
                self.env['mail.mail'].create(mail_values).send()
                
                self.last_summary_notification_date = datetime.now()
                _logger.info("Sent %s notification for screening %s with %d candidates (showing top %d)", 
                           frequency_label, self.name, total_found, len(high_scoring_applicants))
        except Exception as e:
            _logger.error("Error sending summary notification for screening %s: %s", self.name, str(e))

    def _score_resume(self, resume_text, model):
        """Calculate ATS-compatible score using configured weights."""
        # Get weights (normalize if total doesn't equal 100)
        total_weight = (self.keyword_score_weight + self.experience_score_weight + 
                       self.structure_score_weight + self.ai_prediction_weight) or 100
        weight_factor = 100.0 / total_weight if total_weight > 0 else 1.0
        
        # Keyword matching with lemmatization
        lemmatizer = WordNetLemmatizer()
        keywords = [lemmatizer.lemmatize(kw.name.lower()) for kw in self.keyword_ids]
        resume_words = set([lemmatizer.lemmatize(word) for word in
                            re.findall(r'\w+', resume_text.lower())])
        keyword_match_ratio = (sum(1 for kw in keywords if kw in resume_words) / len(
            keywords)) if keywords else 0
        keyword_score = keyword_match_ratio * (self.keyword_score_weight * weight_factor)

        # Experience matching
        experience = self._extract_years_experience(resume_text)
        experience_ratio = min(experience / (self.min_years_experience or 1), 1)
        experience_score = experience_ratio * (self.experience_score_weight * weight_factor)

        # Structure score
        structure_ratio = self._evaluate_structure(resume_text)
        structure_score = structure_ratio * (self.structure_score_weight * weight_factor)

        # AI prediction
        proba = model.predict_proba([resume_text])[0]
        ai_ratio = (proba[1] if len(proba) > 1 else proba[0])
        ai_prediction = ai_ratio * (self.ai_prediction_weight * weight_factor)

        total_score = keyword_score + experience_score + structure_score + ai_prediction
        return min(total_score, 100)

    def _extract_years_experience(self, text):
        """Extract years of experience from text."""
        patterns = [
            r'(\d+)\+?\s*years?\s*of?\s*experience',
            r'experience\s*of\s*(\d+)\+?\s*years?',
            r'(\d+)\+?\s*years?\s*experience',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0

    def _evaluate_structure(self, text):
        """Evaluate resume structure for ATS compatibility."""
        score = 0
        sections = ['experience', 'education', 'skills', 'summary', 'certifications']
        text_lower = text.lower()
        for section in sections:
            if section in text_lower:
                score += 0.2  # 20% per section, max 100%
        return min(score, 1.0)


class AIResumeKeyword(models.Model):
    _name = 'ai.resume.keyword'
    _description = 'AI Resume Keyword'

    name = fields.Char(string='Keyword', required=True)


class HRApplicant(models.Model):
    _inherit = 'hr.applicant'

    ai_screening_id = fields.Many2one('ai.resume.screening', string='AI Screening', index=True)
    ai_score = fields.Float(string='AI Score', default=0.0, index=True, store=True, 
                           help='AI-generated score for the resume (0-100)')
    ai_score_range = fields.Selection([
        ('excellent', 'Excellent (≥90)'),
        ('great', 'Great (≥80)'),
        ('good', 'Good (≥70)'),
        ('fair', 'Fair (≥50)'),
        ('poor', 'Poor (&lt;50)'),
        ('not_scored', 'Not Scored'),
    ], string='AI Score Range', compute='_compute_ai_score_range', 
       store=True, group_expand='_read_group_ai_score_range',
       help='Score range for grouping')
    resume_text = fields.Text(string='Resume Text', compute='_compute_resume_text',
                              store=True)
    resume = fields.Binary(string='Resume', attachment=True)
    auto_screened = fields.Boolean(string='Auto-Screened', default=False, readonly=True)
    screening_date = fields.Datetime(string='Screening Date', readonly=True)

    @api.depends('resume')
    def _compute_resume_text(self):
        """Extract resume text efficiently."""
        for applicant in self:
            if applicant.resume and not applicant.resume_text:  # Only recompute if empty
                try:
                    resume_bytes = base64.b64decode(applicant.resume)
                    with pdfplumber.open(BytesIO(resume_bytes)) as pdf:
                        text = "".join(page.extract_text() or "" for page in pdf.pages)
                    applicant.resume_text = text if text.strip() else "Error: No readable text found in the resume."
                except Exception as e:
                    _logger.error("Error extracting text from resume: %s", str(e))
                    applicant.resume_text = "Error: Unable to extract text from the resume."
            elif not applicant.resume:
                applicant.resume_text = False
    
    @api.depends('ai_score')
    def _compute_ai_score_range(self):
        """Compute AI score range for grouping."""
        for applicant in self:
            if not applicant.ai_score or applicant.ai_score == 0:
                applicant.ai_score_range = 'not_scored'
            elif applicant.ai_score >= 90:
                applicant.ai_score_range = 'excellent'
            elif applicant.ai_score >= 80:
                applicant.ai_score_range = 'great'
            elif applicant.ai_score >= 70:
                applicant.ai_score_range = 'good'
            elif applicant.ai_score >= 50:
                applicant.ai_score_range = 'fair'
            else:
                applicant.ai_score_range = 'poor'
    
    @api.model
    def _read_group_ai_score_range(self, groups, domain, order):
        """Group expand method to show all score ranges even if empty."""
        # Return all possible values to show in group by even if no records exist
        return ['excellent', 'great', 'good', 'fair', 'poor', 'not_scored']
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure candidate linkage (Odoo 19) and trigger auto-screening."""
        # Odoo 19: Handle candidate_id if hr.candidate model exists (optional in some versions)
        if 'hr.candidate' in self.env:
            Candidate = self.env['hr.candidate']
            existing_candidate = Candidate.search([], limit=1)
            for vals in vals_list:
                # If candidate_id not provided (e.g., demo data), link to an existing candidate
                if not vals.get('candidate_id') and existing_candidate:
                    vals['candidate_id'] = existing_candidate.id

        applicants = super().create(vals_list)
        for applicant in applicants:
            if applicant.ai_screening_id and applicant.resume:
                # Trigger resume text extraction
                applicant._compute_resume_text()
                # Auto-screen if enabled
                if (applicant.ai_screening_id.auto_screen_enabled and 
                    applicant.ai_screening_id.model_trained and
                    applicant.ai_screening_id.model_data):
                    applicant._auto_screen_if_ready()
        return applicants
    
    def write(self, vals):
        """Override write to trigger auto-screening when resume or screening is added."""
        result = super().write(vals)
        if 'resume' in vals or 'ai_screening_id' in vals:
            for applicant in self:
                if applicant.ai_screening_id and applicant.resume:
                    # Trigger resume text extraction
                    applicant._compute_resume_text()
                    # Auto-screen if enabled
                    if (applicant.ai_screening_id.auto_screen_enabled and 
                        applicant.ai_screening_id.model_trained and
                        applicant.ai_screening_id.model_data):
                        applicant._auto_screen_if_ready()
        return result
    
    def _auto_screen_if_ready(self):
        """Auto-screen applicant if conditions are met."""
        if (self.resume_text and 
            self.resume_text != "Error: Unable to extract text from the resume." and
            (not self.ai_score or self.ai_score == 0) and
            self.ai_screening_id.model_trained and
            self.ai_screening_id.model_data):
            try:
                model = self.ai_screening_id._get_model()
                self.ai_score = self.ai_screening_id._score_resume(self.resume_text, model)
                self.auto_screened = True
                self.screening_date = datetime.now()
                self._update_status_from_score()
                # Send notification if enabled
                if (self.ai_screening_id.email_notification_enabled and 
                    self.ai_score >= self.ai_screening_id.high_score_threshold):
                    self._send_high_score_notification()
            except Exception as e:
                _logger.error("Error auto-screening applicant %s: %s", self.name, str(e))
    
    def _update_status_from_score(self):
        """Update applicant status based on AI score."""
        if not self.ai_score:
            return
        
        # Check if hr.recruitment.stage model exists
        if 'hr.recruitment.stage' not in self.env:
            return
        
        # Map scores to stages (customize based on your workflow)
        if self.ai_score >= 80:
            # High score - move to qualified stage if exists
            try:
                qualified_stage = self.env['hr.recruitment.stage'].search([
                    ('name', 'ilike', 'qualified'),
                    ('job_id', '=', self.job_id.id)
                ], limit=1)
                if qualified_stage:
                    self.stage_id = qualified_stage.id
            except Exception:
                pass
        elif self.ai_score < 50:
            # Low score - move to rejected stage if exists
            try:
                rejected_stage = self.env['hr.recruitment.stage'].search([
                    ('name', 'ilike', 'rejected'),
                    ('job_id', '=', self.job_id.id)
                ], limit=1)
                if rejected_stage:
                    self.stage_id = rejected_stage.id
            except Exception:
                pass
    
    def _send_high_score_notification(self):
        """Send email notification for high-scoring candidates."""
        if not self.ai_screening_id.notification_recipient_ids:
            return
        
        try:
            # Use the correct XML ID for this module's email template
            mail_template = self.env.ref('ai_resume_analyzer_screening_odoo.email_template_high_score', False)
            if not mail_template:
                # Create basic email notification
                subject = f"High-Scoring Candidate: {self.name} - Score: {self.ai_score:.1f}"
                body = f"""
                <p>A new high-scoring candidate has been identified:</p>
                <ul>
                    <li><strong>Name:</strong> {self.name}</li>
                    <li><strong>Email:</strong> {self.email_from or 'N/A'}</li>
                    <li><strong>Position:</strong> {self.job_id.name if self.job_id else 'N/A'}</li>
                    <li><strong>AI Score:</strong> {self.ai_score:.1f}/100</li>
                </ul>
                <p>Please review this candidate in the recruitment module.</p>
                """
                
                mail_values = {
                    'subject': subject,
                    'body_html': body,
                    'email_to': ','.join([user.email for user in self.ai_screening_id.notification_recipient_ids if user.email]),
                    'email_from': self.env.user.email or self.env.company.email,
                }
                self.env['mail.mail'].create(mail_values).send()
            else:
                mail_template.send_mail(self.id, force_send=True)
            
            _logger.info("Sent high-score notification for applicant %s", self.name)
        except Exception as e:
            _logger.error("Error sending notification for applicant %s: %s", self.name, str(e))


class HRJob(models.Model):
    _inherit = 'hr.job'

    ai_screening_ids = fields.One2many('ai.resume.screening', 'job_position_id',
                                       string='AI Screenings')
    ai_screening_count = fields.Integer(string='AI Screenings Count', compute='_compute_ai_screening_info', store=False)
    ai_screening_trained = fields.Boolean(string='AI Model Trained', compute='_compute_ai_screening_info', store=False)
    ai_screening_applicant_count = fields.Integer(string='Screened Applicants', compute='_compute_ai_screening_info', store=False)
    ai_screening_avg_score = fields.Float(string='Avg AI Score', compute='_compute_ai_screening_info', store=False)

    @api.depends('ai_screening_ids', 'ai_screening_ids.model_trained', 'ai_screening_ids.applicant_ids', 'ai_screening_ids.applicant_ids.ai_score')
    def _compute_ai_screening_info(self):
        """Compute AI screening statistics for kanban view."""
        for job in self:
            screenings = job.ai_screening_ids
            job.ai_screening_count = len(screenings)
            job.ai_screening_trained = any(screenings.mapped('model_trained'))
            all_applicants = screenings.mapped('applicant_ids').filtered(lambda a: a.ai_score > 0)
            job.ai_screening_applicant_count = len(all_applicants)
            if all_applicants:
                job.ai_screening_avg_score = sum(all_applicants.mapped('ai_score')) / len(all_applicants)
            else:
                job.ai_screening_avg_score = 0.0

    def action_open_ai_screening(self):
        self.ensure_one()
        existing_screening = self.ai_screening_ids[:1] or False
        return {
            'name': 'AI Resume Screening',
            'type': 'ir.actions.act_window',
            'res_model': 'ai.resume.screening',
            'view_mode': 'form',
            'target': 'current',
            'res_id': existing_screening.id if existing_screening else False,
            'context': {
                'default_job_position_id': self.id,
                'default_name': f"Screening for {self.name}"
            } if not existing_screening else {},
        }

    @api.model
    def _action_load_ai_screening_scenario(self):
        """Load sample AI screening data from scenario XML file."""
        convert_file(
            self.sudo().env,
            "ai_resume_analyzer_screening_odoo",
            "data/scenarios/ai_resume_screening_scenario.xml",
            None,
            mode="init",
        )
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    @api.model
    def _action_load_recruitment_scenario(self):
        """Extend hr_recruitment sample loader to also load AI screening scenario."""
        # First, call the original hr_recruitment implementation to load its sample data
        action = super()._action_load_recruitment_scenario()

        # Then load our AI Resume Screening scenario so both datasets are available together
        convert_file(
            self.sudo().env,
            "ai_resume_analyzer_screening_odoo",
            "data/scenarios/ai_resume_screening_scenario.xml",
            None,
            mode="init",
        )

        return action


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _add_ai_score_to_applicant_tree(self):
        """Add AI Score field to hr.applicant tree views."""
        try:
            # Check if hr.applicant model exists
            if 'hr.applicant' not in self.env:
                _logger.warning("hr.applicant model not found. Skipping AI Score field addition.")
                return
            
            # Find all tree views for hr.applicant
            tree_views = self.search([
                ('model', '=', 'hr.applicant'),
                ('type', '=', 'list')
            ])
            
            for view in tree_views:
                try:
                    arch_str = view.arch_db or view.arch
                    if not arch_str:
                        continue
                    
                    arch = etree.fromstring(arch_str)
                    # Odoo 19 uses 'list' view type (Odoo 17 and earlier used 'tree')
                    list_elem = arch.xpath('//list')
                    
                    if not list_elem:
                        continue
                    
                    # Check if fields already exist
                    existing_ai_score = list_elem[0].xpath(".//field[@name='ai_score']")
                    existing_auto_screened = list_elem[0].xpath(".//field[@name='auto_screened']")
                    existing_screening_date = list_elem[0].xpath(".//field[@name='screening_date']")
                    
                    # Find email_from field to insert after
                    email_field = list_elem[0].xpath(".//field[@name='email_from']")
                    if not email_field:
                        # Try partner_name or name as fallback
                        partner_field = list_elem[0].xpath(".//field[@name='partner_name']")
                        if partner_field:
                            email_field = partner_field
                        else:
                            name_field = list_elem[0].xpath(".//field[@name='name']")
                            if name_field:
                                email_field = name_field
                            else:
                                continue
                    
                    insert_position = email_field[0]
                    fields_added = False
                    
                    # Add ai_score field if it doesn't exist
                    if not existing_ai_score:
                        ai_score_elem = etree.Element('field', name='ai_score')
                        ai_score_elem.set('widget', 'float')
                        ai_score_elem.set('optional', 'show')
                        ai_score_elem.set('decoration-success', 'ai_score >= 70')
                        ai_score_elem.set('decoration-warning', 'ai_score >= 50 and ai_score < 70')
                        ai_score_elem.set('decoration-danger', 'ai_score < 50')
                        insert_position.addnext(ai_score_elem)
                        insert_position = ai_score_elem
                        fields_added = True
                    else:
                        insert_position = existing_ai_score[0]
                    
                    # Add auto_screened field if it doesn't exist
                    if not existing_auto_screened:
                        auto_screened_elem = etree.Element('field', name='auto_screened')
                        auto_screened_elem.set('widget', 'boolean')
                        auto_screened_elem.set('optional', 'show')
                        insert_position.addnext(auto_screened_elem)
                        insert_position = auto_screened_elem
                        fields_added = True
                    elif not fields_added:
                        insert_position = existing_auto_screened[0]
                    
                    # Add screening_date field if it doesn't exist
                    if not existing_screening_date:
                        screening_date_elem = etree.Element('field', name='screening_date')
                        screening_date_elem.set('optional', 'show')
                        insert_position.addnext(screening_date_elem)
                        fields_added = True
                    
                    if not fields_added:
                        continue
                    
                    # Update the view
                    view.write({'arch_db': etree.tostring(arch, encoding='unicode')})
                    _logger.info("Added AI Score field to view %s (ID: %s)", view.name, view.id)
                except Exception as e:
                    _logger.warning("Error updating view %s: %s", view.name, str(e))
        except Exception as e:
            _logger.error("Error adding AI Score to applicant tree views: %s", str(e))
    