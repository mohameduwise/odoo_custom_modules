from odoo import http
from odoo.http import request
import base64
import json

class SurveyFileController(http.Controller):
    
    @http.route('/survey/upload_file', type='http', auth='public', methods=['POST'], csrf=False)
    def upload_file(self, **kwargs):
        try:
            file = request.httprequest.files.get('file')
            if not file:
                return json.dumps({'error': 'No file provided'})
            
            # Create temporary attachment
            attachment = request.env['ir.attachment'].sudo().create({
                'name': file.filename,
                'datas': base64.b64encode(file.read()),
                'res_model': 'survey.user_input.line',
                'public': False,
            })
            
            return json.dumps({'attachment_id': attachment.id, 'filename': file.filename})
        except Exception as e:
            return json.dumps({'error': str(e)})
    
    @http.route('/survey/save_signature', type='jsonrpc', auth='public', methods=['POST'])
    def save_signature(self, signature_data, question_id, **kwargs):
        try:
            if not signature_data or not signature_data.startswith('data:image/'):
                return {'error': 'Invalid signature data'}
            
            # Extract base64 data from data URL
            header, data = signature_data.split(',', 1)
            image_data = base64.b64decode(data)
            
            # Create attachment for signature
            attachment = request.env['ir.attachment'].sudo().create({
                'name': f'signature_question_{question_id}.png',
                'datas': base64.b64encode(image_data),
                'res_model': 'survey.user_input.line',
                'mimetype': 'image/png',
                'public': False,
            })
            
            return {'attachment_id': attachment.id, 'success': True}
        except Exception as e:
            return {'error': str(e)}