from odoo import models, fields, _
from odoo.exceptions import UserError

class ApplicantLinkWizard(models.TransientModel):
    _name = 'hr.applicant.oad.wizard'
    _description = 'Send Link to Applicant'

    applicant_id = fields.Many2one('hr.applicant', string='Applicant', required=True)
    link = fields.Char(string='Link', required=True)

    def action_send_link(self):
        self.ensure_one()
        applicant = self.applicant_id

        if not applicant.email_from:
            raise UserError(_("The applicant does not have an email address."))

        sender = (
            applicant.user_id.partner_id.email
            or self.env.user.partner_id.email
            or 'no-reply@insytx.com'
        )

        job_name = applicant.job_id.name or "this position"
        candidate = applicant.partner_name or "Candidate"

        subject = f"Final Profiling: OAD Strategic Alignment | {job_name}"

        body_html = f"""
        <div style="font-family: Arial, sans-serif; font-size:14px; color:#000; line-height:1.6;">
            <p>Dear <strong>{candidate}</strong>,</p>

            <p>
                Congratulations on reaching this important milestone in our selection process.
                Based on your strong performance across technical and behavioral evaluations,
                you are now moving into the final assessment phase.
            </p>

            <p>
                This phase involves completing the <strong>OAD (Organization Analysis Design) Profile</strong>,
                a scientifically designed survey that helps us determine how well your natural
                work style aligns with the requirements of the <strong>{job_name}</strong> role.
            </p>

            <p>
                At INSYTX, we replace guesswork with precision.  
                The OAD profile ensures that both you and the organization are positioned for
                long-term success, satisfaction, and high performance.
            </p>

            <h3 style="color:#007bff;">Why this matters</h3>
            <ul>
                <li><strong>Scientific Alignment</strong> – Your behavioral strengths are matched against real job demands.</li>
                <li><strong>Mutual Success</strong> – The right role ensures faster growth and stronger contribution.</li>
                <li><strong>Career Insight</strong> – You gain a clear view of your professional working style.</li>
            </ul>

            <h3 style="color:#007bff;">Complete Your OAD Profile</h3>
            <div style="margin:20px 0; text-align:center;">
                <a href="{self.link}"
                   style="background:#875A7B; color:#ffffff; padding:12px 26px;
                          text-decoration:none; border-radius:6px; font-size:15px; display:inline-block;">
                    Start OAD Survey
                </a>
            </div>

            <p>
                The survey takes approximately <strong>5 minutes</strong>.  
                Please answer honestly and instinctively — there are no right or wrong answers.
            </p>

            <p>
                Once your results are analyzed, our team will contact you regarding the next step:
                your One-to-One interview.
            </p>

            <p style="margin-top:30px;">
                Best regards,<br/>
                <strong>Talent Acquisition Team</strong><br/>
                INSYTX
            </p>
        </div>
        """

        mail = self.env['mail.mail'].sudo().create({
            'email_from': sender,
            'email_to': applicant.email_from,
            'subject': subject,
            'body_html': body_html,
        })

        mail.send()
