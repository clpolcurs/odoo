# -*- coding: utf-8 -*-
# Copyright (C) InTechual Solutions (<https://intechualsolutions.com>). All Rights Reserved

from odoo import api, fields, models, _


class Partner(models.Model):
    _inherit = "res.partner"

    demo_audio_field = fields.Binary(string='Demo Audio Field')
