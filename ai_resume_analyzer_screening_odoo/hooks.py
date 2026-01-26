# -*- coding: utf-8 -*-

def post_init_hook(env):
    """Add AI Score field to hr.applicant tree views after module installation and train demo models."""
    # In newer Odoo versions (v14+), post_init_hook receives env directly
    env['ir.ui.view']._add_ai_score_to_applicant_tree()
    # Note: AI Screening fields for hr.job are now handled via XML view inheritance
    
    # Train models for demo screening records that have enough applicants
    screening_model = env['ai.resume.screening']
    demo_screenings = screening_model.search([
        ('model_trained', '=', True)
    ])
    
    for screening in demo_screenings:
        try:
            # Ensure resume_text is computed for all applicants
            for applicant in screening.applicant_ids:
                if applicant.resume and not applicant.resume_text:
                    applicant._compute_resume_text()
            
            # Check if we have enough applicants with scores to train
            applicants_with_scores = screening.applicant_ids.filtered(
                lambda a: a.resume_text and a.ai_score is not None and a.ai_score > 0 and 
                         a.resume_text != "Error: Unable to extract text from the resume."
            )
            if len(applicants_with_scores) >= 2:
                screening.train_model()
            else:
                # Not enough data, set model_trained to False
                screening.model_trained = False
        except Exception as e:
            # If training fails, set model_trained to False
            screening.model_trained = False
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Failed to train model for demo screening %s: %s", screening.name, str(e))

