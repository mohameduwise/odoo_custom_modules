from odoo import models, fields, api,_
import os
import base64
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _get_report_image_b64_quotation(self, filename):
        """
        Reads an image from the module's static/src/img/ folder
        and returns it as a base64 data URI string for use in QWeb PDF reports.
        wkhtmltopdf cannot fetch /static/ URLs directly, so we embed as base64.
        """
        if self.state not in ('draft'):
            raise UserError(
                _("Quotation report can only be printed for Draft orders.\n"
                  "'%s' is currently in '%s' state.")
                % (self.name, self.state)
            )
        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')

        return ''

    @api.model
    def _get_report_image_b64_sale_order(self, filename):
        """
        Reads an image from the module's static/src/img/ folder
        and returns it as a base64 data URI string for use in QWeb PDF reports.
        wkhtmltopdf cannot fetch /static/ URLs directly, so we embed as base64.
        Raises UserError if the order is not in confirmed state.
        """
        # Validation: only allow printing for confirmed/done orders
        if self.state not in ('sale', 'done'):
            raise UserError(
                _("Sale Order report can only be printed for confirmed orders.\n"
                  "'%s' is currently in '%s' state. Please confirm the order first.")
                % (self.name, self.state)
            )

        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')
        return ''

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_report_image_b64_invoice(self, filename):
        """
        Reads an image from the module's static/src/img/ folder
        and returns it as a base64 data URI string for use in QWeb PDF reports.
        wkhtmltopdf cannot fetch /static/ URLs directly, so we embed as base64.
        """
        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')

        return ''
    @api.model
    def _get_report_image_b64_cash_sales(self, filename):
        """
        Reads an image from the module's static/src/img/ folder
        and returns it as a base64 data URI string for use in QWeb PDF reports.
        wkhtmltopdf cannot fetch /static/ URLs directly, so we embed as base64.
        """
        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')

        return ''

    def _get_report_image_b64_deposit_invoice(self, filename):
        """Only allowed when invoice is partially paid."""
        if self.payment_state not in ('partial',):
            raise UserError(
                _("Deposit Invoice report can only be printed when the invoice is partially paid.\n"
                  "'%s' payment state is '%s'.")
                % (self.name, self.payment_state)
            )
        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')
        return ''

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def _get_report_image_b64_rfq(self, filename):
        """
        Reads an image from the module's static/src/img/ folder
        and returns it as a base64 data URI string for use in QWeb PDF reports.
        wkhtmltopdf cannot fetch /static/ URLs directly, so we embed as base64.
        """
        if self.state not in ('draft'):
            raise UserError(
                _("RFQ report can only be printed for Draft orders.\n"
                  "'%s' is currently in '%s' state.")
                % (self.name, self.state)
            )
        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')

        return ''

    @api.model
    def _get_report_image_b64_purchase_order(self, filename):
        """
        Reads an image from the module's static/src/img/ folder
        and returns it as a base64 data URI string for use in QWeb PDF reports.
        wkhtmltopdf cannot fetch /static/ URLs directly, so we embed as base64.
        Raises UserError if the order is not in confirmed state.
        """
        # Validation: only allow printing for confirmed/done orders
        if self.state not in 'purchase':
            raise UserError(
                _("Purchase Order report can only be printed for confirmed orders.\n"
                  "'%s' is currently in '%s' state. Please confirm the order first.")
                % (self.name, self.state)
            )

        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')
        return ''

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_report_image_b64_delivery_order(self, filename):
        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'src', 'img', filename
        )
        if os.path.exists(module_path):
            with open(module_path, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')
        return ''

