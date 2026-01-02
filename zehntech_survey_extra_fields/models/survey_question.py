# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re
from datetime import datetime


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    question_type = fields.Selection(
        selection_add=[
            ('color', 'Color'),
            ('email', 'Email'),
            ('url', 'URL'), 
            ('time', 'Time'),
            ('range', 'Range'),
            ('week', 'Week'),
            ('password', 'Password'),
            ('file', 'File'),
            ('signature', 'Signature'),
            ('month', 'Month'),
            ('address', 'Address'),
            ('name', 'Name'),
            ('many2one', 'Many2one'),
            ('many2many', 'Many2many'),
        ],
        ondelete={
            'color': 'cascade',
            'email': 'cascade',
            'url': 'cascade',
            'time': 'cascade',
            'range': 'cascade',
            'week': 'cascade',
            'password': 'cascade',
            'file': 'cascade',
            'signature': 'cascade',
            'month': 'cascade',
            'address': 'cascade',
            'name': 'cascade',
            'many2one': 'cascade',
            'many2many': 'cascade',
        }
    )



    # Time field specific
    time_validate = fields.Boolean('Enable Validation')
    time_min = fields.Char('Min Time (HH:MM)')
    time_max = fields.Char('Max Time (HH:MM)')
    time_step = fields.Integer('Time Step (minutes)', default=15)
    time_error_msg = fields.Char('Validation Error Message', default="Invalid time selected")

    # Range field specific
    range_min = fields.Float('Range Min', default=0)
    range_max = fields.Float('Range Max', default=100)
    range_step = fields.Float('Range Step', default=1)
    validate_range = fields.Boolean('Validate Entry')

    # Week field specific
    validate_week_entry = fields.Boolean('Validate Week Entry', default=True)
    week_min = fields.Char('Min Week', help="Minimum selectable week (YYYY-WW)")
    week_max = fields.Char('Max Week', help="Maximum selectable week (YYYY-WW)")
    week_step = fields.Integer('Week Step', default=1, help="Step between selectable weeks")
    week_error_msg = fields.Char('Week Validation Error', default='Invalid week value.')

    # Password specific
    validate_password = fields.Boolean('Validate Password Entry', default=True)
    password_min_length = fields.Integer('Min Password Length', default=1)
    password_max_length = fields.Integer('Max Password Length', default=8)
    password_error_msg = fields.Char('Password Validation Error', default='Invalid password length.')

     # File field specific
    file_max_size = fields.Float('Max File Size (MB)', default=10.0)
    file_allowed_types = fields.Char('Allowed File Types', help="Comma-separated extensions (e.g., pdf,jpg,png)")

    # Signature field specific
    signature_width = fields.Integer('Canvas Width', default=400)
    signature_height = fields.Integer('Canvas Height', default=200)

    # Month field specific
    validate_month_entry = fields.Boolean('Validate Entry', default=True)
    month_min = fields.Char('Min Month', help="Minimum selectable month (YYYY-MM)")
    month_max = fields.Char('Max Month', help="Maximum selectable month (YYYY-MM)")
    month_step = fields.Integer('Month Step', default=1, help="Step between selectable months")
    month_error_msg = fields.Char('Month Validation Error', default='Invalid month value.')

    # Address field specific
    address_enable_street = fields.Boolean('Enable Street', default=True)
    address_enable_street2 = fields.Boolean('Enable Street 2', default=True)
    address_enable_zip = fields.Boolean('Enable Zip', default=True)
    address_enable_city = fields.Boolean('Enable City', default=True)
    address_enable_state = fields.Boolean('Enable State', default=True)
    address_enable_country = fields.Boolean('Enable Country', default=True)
    address_label_street = fields.Char('Street Label', default='Street')
    address_label_street2 = fields.Char('Street 2 Label', default='Street 2')
    address_label_zip = fields.Char('Zip Label', default='Zip')
    address_label_city = fields.Char('City Label', default='City')
    address_label_state = fields.Char('State Label', default='State')
    address_label_country = fields.Char('Country Label', default='Country')

    # Name field specific
    name_middle_optional = fields.Boolean('Middle Name Optional', default=True, help="If enabled, middle name is optional even when question is mandatory")

    # Many2one field specific
    many2one_model = fields.Char('Model Name', help="Model to select records from (e.g., res.partner)")

    # Many2many field specific
    many2many_model = fields.Char('Model Name', help="Model to select records from (e.g., res.partner)")


    # -------------------------
    # Time Field Config Check
    # -------------------------
    @api.constrains('time_min', 'time_max', 'time_step')
    def _check_time_format(self):
        for question in self:
            if question.question_type == 'time':
                # Validate time format for each relevant field
                for field_name in ['time_min', 'time_max']:
                    value = getattr(question, field_name)
                    if value:
                        try:
                            datetime.strptime(value, "%H:%M")
                        except ValueError:
                            raise ValidationError(_("%s must be in HH:MM format") % field_name)

                # Validate time order and step logic
                if question.time_min and question.time_max:
                    min_time = datetime.strptime(question.time_min, "%H:%M")
                    max_time = datetime.strptime(question.time_max, "%H:%M")

                    # Ensure max is not before min
                    if max_time < min_time:
                        raise ValidationError(_("Time Max cannot be earlier than Time Min."))

                    # Validate step compatibility (step must fit in range)
                    if question.time_step and question.time_step > 0:
                        total_minutes = int((max_time - min_time).total_seconds() / 60)
                        if total_minutes < question.time_step:
                            raise ValidationError(_(
                                "Time Step must be smaller than or equal to the difference "
                                "between Time Min and Time Max."
                            ))

                # Ensure step is positive
                if question.time_step is not None and question.time_step <= 0:
                    raise ValidationError(_("Time Step must be greater than 0."))


    # -------------------------
    # Range Field Config Check
    # -------------------------
    @api.constrains('range_min', 'range_max', 'range_step')
    def _check_range_config(self):
        for question in self:
            if question.question_type == 'range':
                if question.range_max < question.range_min:
                    raise ValidationError(_("Range Max cannot be less than Range Min."))
                if question.range_step <= 0:
                    raise ValidationError(_("Range Step must be greater than 0."))
                if question.range_step > (question.range_max - question.range_min):
                    raise ValidationError(_("Range Step cannot be greater than the range (Max - Min)."))

    # -------------------------
    # Week Field Config Check
    # -------------------------
    @api.constrains('week_min', 'week_max', 'week_step')
    def _check_week_config(self):
        week_regex = r'^\d{4}-W\d{2}$'
        for question in self:
            if question.question_type == 'week':
                min_val = question.week_min
                max_val = question.week_max
                if min_val and not re.match(week_regex, min_val):
                    raise ValidationError(_("Min Week must be in YYYY-WW format."))
                if max_val and not re.match(week_regex, max_val):
                    raise ValidationError(_("Max Week must be in YYYY-WW format."))
                if min_val and max_val:
                    min_year, min_week = map(int, min_val.split('-W'))
                    max_year, max_week = map(int, max_val.split('-W'))
                    min_date = datetime.strptime(f'{min_year}-W{min_week}-1', "%Y-W%W-%w")
                    max_date = datetime.strptime(f'{max_year}-W{max_week}-1', "%Y-W%W-%w")
                    if max_date < min_date:
                        raise ValidationError(_("Max Week cannot be earlier than Min Week."))
                    
                    # Calculate total number of weeks in the range
                    total_weeks = (max_year - min_year) * 52 + (max_week - min_week) + 1
                    if question.week_step > total_weeks:
                        raise ValidationError(_("Week Step cannot be greater than the total number of weeks in the range."))
                    
                if question.week_step <= 0:
                    raise ValidationError(_("Week Step must be greater than 0."))

    # -------------------------
    # Password Field Config Check
    # -------------------------
                
    @api.constrains('password_min_length', 'password_max_length')
    def _check_password_limits(self):
        for question in self:
            if question.question_type == 'password':
                if question.password_min_length < 1:
                    raise ValidationError(_("Minimum password length must be at least 1."))
                if question.password_max_length < question.password_min_length:
                    raise ValidationError(_("Maximum password length cannot be less than minimum length."))
                
    @api.constrains('file_max_size')
    def _check_file_size(self):
        for question in self:
            if question.question_type == 'file' and question.file_max_size <= 0:
                raise ValidationError(_('File size must be greater than 0 MB.'))

    # -------------------------
    # Month Field Config Check
    # -------------------------
    @api.constrains('month_min', 'month_max', 'month_step')
    def _check_month_config(self):
        month_regex = r'^\d{4}-(0[1-9]|1[0-2])$'  # Strict month validation (01-12)
        for question in self:
            if question.question_type == 'month':
                min_val = question.month_min
                max_val = question.month_max
                if min_val and not re.match(month_regex, min_val):
                    raise ValidationError(_("Min Month must be in YYYY-MM format with valid month (01-12)."))
                if max_val and not re.match(month_regex, max_val):
                    raise ValidationError(_("Max Month must be in YYYY-MM format with valid month (01-12)."))
                if min_val and max_val and min_val > max_val:
                    raise ValidationError(_("Max Month cannot be earlier than Min Month."))
                if question.month_step <= 0:
                    raise ValidationError(_("Month Step must be greater than 0."))
                
                # Validate step against range
                if min_val and max_val and question.month_step > 1:
                    min_year, min_month = map(int, min_val.split('-'))
                    max_year, max_month = map(int, max_val.split('-'))
                    total_months = (max_year - min_year) * 12 + (max_month - min_month)
                    if question.month_step > total_months:
                        raise ValidationError(_("Month Step (%s) cannot be greater than the total months in range (%s).") % (question.month_step, total_months))

    # -------------------------
    # Address Field Config Check
    # -------------------------
    @api.constrains('address_enable_street', 'address_enable_street2', 'address_enable_zip', 'address_enable_city', 'address_enable_state', 'address_enable_country')
    def _check_address_config(self):
        for question in self:
            if question.question_type == 'address':
                enabled_fields = [
                    question.address_enable_street,
                    question.address_enable_street2,
                    question.address_enable_zip,
                    question.address_enable_city,
                    question.address_enable_state,
                    question.address_enable_country
                ]
                if not any(enabled_fields):
                    raise ValidationError(_('At least one address sub-field must be enabled.'))

    # -------------------------
    # Many2one Field Config Check       

    @api.constrains('many2one_model', 'question_type')
    def _check_many2one_model(self):
        for question in self:
            if question.question_type == 'many2one':
                if not question.many2one_model:
                    raise ValidationError(_('Model name is required for Many2one field type.'))
                
                # Convert display name to technical name
                converted_model = question._convert_model_name(question.many2one_model)
                
                # Check if model exists in ir.model (installed)
                model_record = self.env['ir.model'].search([('model', '=', converted_model)], limit=1)
                if not model_record:
                    raise ValidationError(_('Model "%s" does not exist.') % question.many2one_model)
                
                # Check if model is accessible in environment
                try:
                    self.env[converted_model]
                    # Update field with technical name if conversion happened
                    if converted_model != question.many2one_model:
                        question.many2one_model = converted_model
                except KeyError:
                    raise ValidationError(_('Model "%s" is not accessible or has incorrect name.') % question.many2one_model)

    @api.constrains('many2many_model', 'question_type')
    def _check_many2many_model(self):
        for question in self:
            if question.question_type == 'many2many':
                if not question.many2many_model:
                    raise ValidationError(_('Model name is required for Many2many field type.'))
                
                # Convert display name to technical name
                converted_model = question._convert_model_name(question.many2many_model)
                
                # Check if model exists in ir.model (installed)
                model_record = self.env['ir.model'].search([('model', '=', converted_model)], limit=1)
                if not model_record:
                    raise ValidationError(_('Model "%s" does not exist.') % question.many2many_model)
                
                # Check if model is accessible in environment
                try:
                    self.env[converted_model]
                    # Update field with technical name if conversion happened
                    if converted_model != question.many2many_model:
                        question.many2many_model = converted_model
                except KeyError:
                    raise ValidationError(_('Model "%s" is not accessible or has incorrect name.') % question.many2many_model)


    # -------------------------
    # Answer Validations
    # -------------------------
    def validate_question(self, answer, comment=None):
        if self.question_type == 'color':
            return self._validate_color(answer)
        elif self.question_type == 'email':
            return self._validate_email(answer)
        elif self.question_type == 'url':
            return self._validate_url(answer)
        elif self.question_type == 'time':
            return self._validate_time(answer)
        elif self.question_type == 'range':
            return self._validate_range(answer)
        elif self.question_type == 'week':
            return self._validate_week(answer)
        elif self.question_type == 'password':
            return self._validate_password(answer)
        elif self.question_type == 'file':  
            return self._validate_file(answer)
        elif self.question_type == 'signature':
            return self._validate_signature(answer)
        elif self.question_type == 'month':
            return self._validate_month(answer)
        elif self.question_type == 'address':
            return self._validate_address(answer)
        elif self.question_type == 'name':
            return self._validate_name(answer)
        elif self.question_type == 'many2one':
            return self._validate_many2one(answer)
        elif self.question_type == 'many2many':
            return self._validate_many2many(answer)
        return super().validate_question(answer, comment)

    # Color validation
    def _validate_color(self, answer):
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        if answer and not re.match(r'^#[0-9A-Fa-f]{6}$', answer):
            return {self.id: _('Please select a valid color.')}
        return {}

    # Email validation
    def _validate_email(self, answer):
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if answer and not re.match(email_regex, answer):
            return {self.id: _('Please enter a valid email address.')}
        return {}

    # URL validation
    def _validate_url(self, answer):
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        url_regex = r'^https?://[^\s]+$'
        if answer and not re.match(url_regex, answer):
            return {self.id: _('Please enter a valid URL (e.g., https://example.com)')}
        return {}

    # Time validation
    def _validate_time(self, answer):
        if self.constr_mandatory and not answer:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        if not answer:
            return {}
        try:
            time_obj = datetime.strptime(answer.strip(), "%H:%M")
        except ValueError:
            return {self.id: self.time_error_msg or _('Invalid time format (HH:MM).')}
        if self.time_validate:
            if self.time_min and time_obj < datetime.strptime(self.time_min, "%H:%M"):
                return {self.id: self.time_error_msg}
            if self.time_max and time_obj > datetime.strptime(self.time_max, "%H:%M"):
                return {self.id: self.time_error_msg}
            # Step check
            if self.time_step:
                min_time = datetime.strptime(self.time_min or "00:00", "%H:%M")
                diff_minutes = int((time_obj - min_time).total_seconds() / 60)
                if diff_minutes % self.time_step != 0:
                    return {self.id: self.time_error_msg}
        return {}

    # Range validation
    def _validate_range(self, answer):
        if answer is None and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        try:
            val = float(answer)
            if val < self.range_min or val > self.range_max:
                return {self.id: _('Value must be between %s and %s') % (self.range_min, self.range_max)}
            if ((val - self.range_min) % self.range_step) != 0:
                return {self.id: _('Value must respect the step of %s') % self.range_step}
        except (ValueError, TypeError):
            return {self.id: _('Please enter a valid number.')}
        return {}

    # Week validation
    def _validate_week(self, answer):
        if not self.validate_week_entry:
            return {}
        errors = {}
        week_regex = r'^\d{4}-W\d{2}$'
        if not answer:
            if self.constr_mandatory:
                errors[self.id] = self.constr_error_msg or _('This question requires an answer.')
            return errors
        if not re.match(week_regex, answer):
            errors[self.id] = self.week_error_msg or _('Week must be in YYYY-WW format.')
            return errors
        
        year, week = map(int, answer.split('-W'))
        
        # Range validation - check min/max directly
        if self.week_min:
            min_year, min_week = map(int, self.week_min.split('-W'))
            if year < min_year or (year == min_year and week < min_week):
                errors[self.id] = self.week_error_msg or _('Week is before minimum allowed week.')
                return errors
                
        if self.week_max:
            max_year, max_week = map(int, self.week_max.split('-W'))
            if year > max_year or (year == max_year and week > max_week):
                errors[self.id] = self.week_error_msg or _('Week is after maximum allowed week.')
                return errors
        
        # Step validation - only if within range and min is set
        if self.week_min and self.week_step > 1:
            min_year, min_week = map(int, self.week_min.split('-W'))
            weeks_from_min = (year - min_year) * 52 + (week - min_week)
            if weeks_from_min % self.week_step != 0:
                errors[self.id] = self.week_error_msg or _('Week does not match step interval.')
        
        return errors

    # for password validation
    def _validate_password(self, answer):
        """Server-side validation for password field"""
        if not self.validate_password:
            return {}

        if not answer:
            if self.constr_mandatory:
                return {self.id: self.constr_error_msg or _('This question requires a password.')}
            return {}

        if not isinstance(answer, str):
            return {self.id: self.password_error_msg or _('Invalid password format.')}

        length = len(answer.strip())

        if self.password_min_length and length < self.password_min_length:
            return {self.id: self.password_error_msg or _('Password must be at least %s characters.') % self.password_min_length}

        if self.password_max_length and length > self.password_max_length:
            return {self.id: self.password_error_msg or _('Password cannot exceed %s characters.') % self.password_max_length}

        return {}
    
    # for file validation
    def _validate_file(self, answer):
        """File validation"""
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires a file upload.')}
        return {}
    
    # for signature validation
    def _validate_signature(self, answer):
        """Signature validation"""
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires a signature.')}
        # Check if it's a valid signature (base64 data URL or attachment ID)
        if answer and not (answer.startswith('data:image/') or answer.isdigit()):
            return {self.id: _('Invalid signature data.')}
        return {}

    # for month validation
    def _validate_month(self, answer):
        """Month validation - always validates format, range, and step"""
        month_regex = r'^\d{4}-\d{2}$'
        if not answer:
            if self.constr_mandatory:
                return {self.id: self.constr_error_msg or _('This question requires an answer.')}
            return {}
        
        # Always validate format
        if not re.match(month_regex, answer):
            return {self.id: self.month_error_msg or _('Month must be in YYYY-MM format.')}
        
        # Always validate range/step (backend validation)
        # Range validation
        if self.month_min and answer < self.month_min:
            return {self.id: self.month_error_msg or _('Month is before minimum allowed month.')}
        
        if self.month_max and answer > self.month_max:
            return {self.id: self.month_error_msg or _('Month is after maximum allowed month.')}
        
        # Step validation
        if self.month_min and self.month_step > 1:
            min_year, min_month = map(int, self.month_min.split('-'))
            year, month = map(int, answer.split('-'))
            months_from_min = (year - min_year) * 12 + (month - min_month)
            if months_from_min % self.month_step != 0:
                return {self.id: self.month_error_msg or _('Month does not match step interval.')}
        
        return {}

    # Address validation
    def _validate_address(self, answer):
        """Address validation - check if at least one enabled field is filled when mandatory"""
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        
        if answer and self.constr_mandatory:
            # Parse JSON answer to check if at least one enabled field has value
            import json
            try:
                addr_data = json.loads(answer) if isinstance(answer, str) else answer
                enabled_fields = []
                if self.address_enable_street: enabled_fields.append('street')
                if self.address_enable_street2: enabled_fields.append('street2')
                if self.address_enable_zip: enabled_fields.append('zip')
                if self.address_enable_city: enabled_fields.append('city')
                if self.address_enable_state: enabled_fields.append('state')
                if self.address_enable_country: enabled_fields.append('country')
                
                has_value = any(addr_data.get(field, '').strip() for field in enabled_fields)
                if not has_value:
                    return {self.id: self.constr_error_msg or _('At least one address field must be filled.')}
            except (json.JSONDecodeError, AttributeError):
                return {self.id: _('Invalid address format.')}
        
        return {}

    # Name validation
    def _validate_name(self, answer):
        """Name validation - check first and last name when mandatory"""
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        
        if answer and self.constr_mandatory:
            import json
            try:
                name_data = json.loads(answer) if isinstance(answer, str) else answer
                first_name = name_data.get('first_name', '').strip()
                last_name = name_data.get('last_name', '').strip()
                middle_name = name_data.get('middle_name', '').strip()
                
                if not first_name:
                    return {self.id: self.constr_error_msg or _('First name is required.')}
                if not last_name:
                    return {self.id: self.constr_error_msg or _('Last name is required.')}
                if not self.name_middle_optional and not middle_name:
                    return {self.id: self.constr_error_msg or _('Middle name is required.')}
            except (json.JSONDecodeError, AttributeError):
                return {self.id: _('Invalid name format.')}
        
        return {}

    # Many2one validation
    def _validate_many2one(self, answer):
        """Many2one validation - check if selected record exists"""
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        
        if answer and self.many2one_model:
            try:
                record_id = int(answer)
                record = self.env[self.many2one_model].browse(record_id)
                if not record.exists():
                    return {self.id: _('Selected record does not exist.')}
            except (ValueError, KeyError):
                return {self.id: _('Invalid record selection.')}
        
        return {}

    # Many2many validation
    def _validate_many2many(self, answer):
        """Many2many validation - check if selected records exist"""
        if not answer and self.constr_mandatory:
            return {self.id: self.constr_error_msg or _('This question requires an answer.')}
        
        if answer and self.many2many_model:
            try:
                # Answer should be comma-separated IDs or list
                if isinstance(answer, str):
                    record_ids = [int(x.strip()) for x in answer.split(',') if x.strip()]
                else:
                    record_ids = answer if isinstance(answer, list) else [answer]
                
                for record_id in record_ids:
                    record = self.env[self.many2many_model].browse(record_id)
                    if not record.exists():
                        return {self.id: _('Selected record does not exist.')}
            except (ValueError, KeyError):
                return {self.id: _('Invalid record selection.')}
        
        return {}

    def _convert_model_name(self, model_name):
        """Convert display name to technical name by searching ir.model"""
        if not model_name:
            return model_name
        
        # If already technical name, return as is
        try:
            self.env[model_name]
            return model_name
        except KeyError:
            pass
        
        # Search for model by display name
        model_record = self.env['ir.model'].search([
            ('name', '=', model_name)
        ], limit=1)
        
        if model_record:
            return model_record.model
        
        return model_name