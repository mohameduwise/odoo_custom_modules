from odoo import models, fields

class ApplicantLinkWizard(models.TransientModel):
    _name = 'hr.applicant.oad.wizard'
    _description = 'Send Link to Applicant'

    applicant_id = fields.Many2one(
        'hr.applicant',
        string='Applicant',
        required=True
    )
    link = fields.Char(string='Link', required=True)

    def action_send_link(self):
        self.ensure_one()
        template = self.env.ref(
            'instix_customisations.mail_template_oad_link',
            raise_if_not_found=False
        )
        if template:
            template.with_context(link=self.link).send_mail(
                self.applicant_id.id,
                force_send=True
            )