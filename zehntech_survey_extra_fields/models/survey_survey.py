# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    enable_cron = fields.Boolean('Enable Cron')
    scheduled_date = fields.Datetime('Scheduled Date')
    cron_status = fields.Selection([
        ('pending', 'In Progress'),
        ('done', 'Done')
    ], string='Cron Status', readonly=True, default='pending')
    existing_contact_ids = fields.Many2many('res.partner', string='Existing Contacts')

    @api.constrains('enable_cron', 'scheduled_date', 'existing_contact_ids', 'access_mode')
    def _check_cron_access_mode(self):
        for survey in self:
            if survey.enable_cron and survey.access_mode != 'token':
                raise ValidationError(_('Enable Cron is only available when Access Mode is "Invited people only".'))
            
             # Rule 1: If enable_cron is True, scheduled_date is mandatory
            if survey.enable_cron and not survey.scheduled_date:
                raise ValidationError(_('Scheduled Date is mandatory if "Enable Cron" is selected.'))

            # Rule 2: If scheduled_date is set, at least one contact must be selected
            if survey.scheduled_date and not survey.existing_contact_ids:
                raise ValidationError(_('You must select at least one contact if Scheduled Date is set.'))

    @api.model
    def _cron_send_scheduled_surveys(self):
        """Cron job to send scheduled surveys using template rendering"""
        now = fields.Datetime.now()
        surveys = self.search([
            ('enable_cron', '=', True),
            ('cron_status', '=', 'pending'),
            ('access_mode', '=', 'token'),
        ])

        # Get the default survey invite template
        mail_template = self.env.ref('survey.mail_template_user_input_invite', raise_if_not_found=True)

        for survey in surveys:
            if not survey.scheduled_date or survey.scheduled_date <= now:
                if survey.existing_contact_ids:
                    for partner in survey.existing_contact_ids:
                        # Create or get survey.user_input for this partner
                        user_input = self.env['survey.user_input'].sudo().search([
                            ('survey_id', '=', survey.id),
                            ('partner_id', '=', partner.id),
                        ], limit=1)
                        if not user_input:
                            user_input = self.env['survey.user_input'].sudo().create({
                                'survey_id': survey.id,
                                'partner_id': partner.id,
                                'email': partner.email,
                            })

                        # Send the email using the template
                        mail_template.sudo().send_mail(user_input.id, force_send=True)
                        _logger.info("Survey '%s' sent to %s via template.", survey.title, partner.email)

                    # Mark cron as done
                    survey.write({'cron_status': 'done'})

    def write(self, vals):
        if 'scheduled_date' in vals:
            for survey in self:
                if survey.cron_status == 'done' and vals.get('scheduled_date'):
                    vals['cron_status'] = 'pending'
        return super().write(vals)

    @api.onchange('access_mode')
    def _onchange_access_mode(self):
        if self.access_mode != 'token':
            self.enable_cron = False
            self.scheduled_date = False
            self.cron_status = 'pending'
            self.existing_contact_ids = False
