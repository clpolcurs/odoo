# -*- coding: utf-8 -*-

{
    "name": "Learning Japanese",
    "category": "Phyto",
    "summary": "Module Learning Japanese",
    "author": "Tăng Tiến Thanh Tùng",
    "version": "1.0",
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
        # security
        "security/ir.model.access.csv",
        "security/security_access_data.xml",
        # views
        "views/llm_config.xml",
        "views/openai_support.xml",
        "views/prompt_request.xml",
        "views/hanviet.xml",
        "views/comprehensive.xml",
        "views/adj_form.xml",
        "views/verb_group.xml",
        "views/verb_form.xml",
        "views/vocabulary.xml",
        "views/context_tag.xml",
        "views/part_of_speech.xml",
        "views/book.xml",
        "views/lesson.xml",
        "views/learning_japanese_menus.xml",
    ],
    "assets": {"web.assets_backend": ["learning_japanese/static/src/css/style.css"]},
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "LGPL-3",
}
