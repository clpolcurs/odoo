# -*- coding: utf-8 -*-

{
    "name": "Learning Japanese",
    "category": "Phyto",
    "summary": "Module Learning Japanese",
    "author": "Tăng Tiến Thanh Tùng",
    "version": "1.1",
    "website": "",
    "description": """
    This is a custom module for learning Japanese
    """,
    "depends": [
        "base",
        "mail",
        "product",
    ],
    "data": [
        # security (groups first: the ACL rows reference them)
        "security/security_access_data.xml",
        "security/ir.model.access.csv",
        # data
        "data/ir_cron.xml",
        # views
        "views/comprehensive_tag.xml",
        "views/llm_config.xml",
        "views/openai_support.xml",
        "views/prompt_request.xml",
        "views/hanviet.xml",
        "views/comprehensive.xml",
        "views/vocabulary.xml",
        "views/context_tag.xml",
        "views/part_of_speech.xml",
        "views/book.xml",
        "views/lesson.xml",
        "views/api_log.xml",
        "views/learning_japanese_menus.xml",
    ],
    "assets": {"web.assets_backend": ["learning_japanese/static/src/css/style.css"]},
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "LGPL-3",
}
