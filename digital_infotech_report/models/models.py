# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartnerI(models.Model):
    _inherit = 'res.partner'


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    multiline_text = fields.Text(string='Multiline Text')