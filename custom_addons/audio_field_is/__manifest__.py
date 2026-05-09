# -*- coding: utf-8 -*-
# Copyright (C) InTechual Solutions (<https://intechualsolutions.com>). All Rights Reserved

{
    'name': 'Audio Field',
    # 'version': '16.0.1.1.0',
    'category': 'Mail',
    'author': 'InTechual Solutions',
    'license': 'OPL-1',
    'summary': 'Audio Field Widget',
    'description': """Audio Field Widget for Odoo""",
    'depends': ['base', 'web'],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'audio_field_is/static/src/css/*.css',
            'audio_field_is/static/src/components/audio_field/*.js',
            'audio_field_is/static/src/components/audio_field/*.xml',
        ],
    },
    'images': ['static/description/main_screenshot.jpg'],
    'application': True,
    'installable': True,
    'auto_install': False,
    'currency': 'EUR',
    'price': 8,
}
