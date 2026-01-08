from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
import base64
import pickle
import logging
from io import BytesIO

import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

_logger = logging.getLogger(__name__)


class ResumeAIModel(models.Model):
    _name = 'resume.ai.model'
    _description = 'Resume AI Training Model'
    _rec_name = 'name'

    name = fields.Char(
        string="Model Name",
        default="Global Resume Screening AI",
        required=True
    )

    model_data = fields.Binary(
        string="Trained Model",
        readonly=True
    )

    trained_on = fields.Integer(
        string="Trained On (Resumes)",
        readonly=True
    )

    trained_date = fields.Datetime(
        string="Last Trained On",
        readonly=True
    )

    active = fields.Boolean(default=True)

    training_resume_ids = fields.One2many(
        'resume.ai.training.data',
        'ai_model_id',
        string="Manual Training Resumes"
    )

    # ------------------------------------------------------------
    # TRAIN AI MODEL
    # ------------------------------------------------------------
    def action_train_model(self):
        self.ensure_one()

        X, y = self._prepare_training_data()

        model = Pipeline([
            ('tfidf', TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words='english'
            )),
            ('classifier', MultinomialNB())
        ])

        model.fit(X, y)

        self.model_data = base64.b64encode(pickle.dumps(model))
        self.trained_on = len(X)
        self.trained_date = fields.Datetime.now()

        _logger.info(
            "Resume AI trained with %s resumes (Model ID: %s)",
            len(X), self.id
        )

    # ------------------------------------------------------------
    # PREPARE TRAINING DATA
    # ------------------------------------------------------------
    def _prepare_training_data(self):
        """
        Training data sources:
        1) Manually uploaded training resumes
        2) Applicant resumes (auto-labelled using ai_score)
        """

        X = []
        y = []

        # --------------------------------------------------
        # 1️⃣ MANUAL TRAINING RESUMES
        # --------------------------------------------------
        for rec in self.training_resume_ids.filtered(
                lambda r: r.resume_text and r.label
        ):
            text = rec.resume_text.strip()
            if not text:
                continue

            X.append(text)
            y.append(1 if rec.label == 'good' else 0)

        # --------------------------------------------------
        # 2️⃣ APPLICANT RESUMES
        # --------------------------------------------------
        applicants = self.env['hr.applicant'].search([
            ('resume_text', '!=', False),
            ('ai_score', '>', 0),
        ])

        for applicant in applicants:
            text = applicant.resume_text.strip()
            if not text:
                continue

            X.append(text)

            pass_score = applicant.job_id.resume_pass_score or 70
            y.append(1 if applicant.ai_score >= pass_score else 0)

        # --------------------------------------------------
        # VALIDATION
        # --------------------------------------------------

        return X, y

    # ------------------------------------------------------------
    # LOAD TRAINED MODEL
    # ------------------------------------------------------------
    def get_model(self):
        self.ensure_one()
        if not self.model_data:
            raise UserError("AI model is not trained yet.")
        return pickle.loads(base64.b64decode(self.model_data))


class ResumeAITrainingData(models.Model):
    _name = 'resume.ai.training.data'
    _description = 'AI Resume Training Data'

    ai_model_id = fields.Many2one(
        'resume.ai.model',
        string="AI Model",
        required=True,
        ondelete='cascade'
    )

    name = fields.Char(
        string="Resume Name",
        required=True
    )

    resume_file = fields.Binary(
        string="Resume (PDF)",
        required=True
    )

    resume_filename = fields.Char(string="File Name")

    resume_text = fields.Text(
        string="Parsed Resume Text",
        readonly=True
    )

    label = fields.Selection([
        ('good', 'Good Resume'),
        ('bad', 'Bad Resume'),
    ], required=True, string="Training Label")

    active = fields.Boolean(default=True)

    # ------------------------------------------------------------
    # PARSE PDF ON UPLOAD
    # ------------------------------------------------------------
    @api.onchange('resume_file')
    def _onchange_resume_file(self):
        if not self.resume_file:
            return

        try:
            pdf_bytes = base64.b64decode(self.resume_file)

            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = "".join(page.extract_text() or "" for page in pdf.pages)

            if not text.strip():
                raise UserError("No readable text found in this resume.")

            self.resume_text = text

        except Exception as e:
            _logger.error("Resume parsing failed: %s", e)
            self.resume_text = False
            raise UserError("Failed to extract text from the resume.")
