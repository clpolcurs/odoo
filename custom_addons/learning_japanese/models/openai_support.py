import re
import logging
import openai
from google import genai
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class PromptRequest(models.Model):
    _name = "learning_japanese.prompt_request"
    _description = "Prompt Request"
    _rec_name = "request"
    _order = "id desc"

    request = fields.Char(string="Request", copy=False)
    content = fields.Text(string="Request Content", copy=False)
    openai_ids = fields.One2many(
        comodel_name="learning_japanese.openai_support",
        inverse_name="prompt_request_id",
        string="OpenAI Support",
    )


class LLMConfig(models.Model):
    _name = "learning_japanese.llm_config"
    _description = "LLM Configuration"

    name = fields.Char(string="Display Name", required=True, help="e.g., GPT-4o High Speed")
    model_code = fields.Char(string="Model Technical Name", required=True, help="e.g., gpt-4o or gemini-1.5-flash")
    provider = fields.Selection(
        selection=[
            ("openAI", "OpenAI"),
            ("gemini", "Gemini"),
        ],
        string="Provider",
        required=True
    )
    is_active = fields.Boolean(default=True)

    def name_get(self):
        """Custom display name: [Provider] Display Name"""
        result = []
        for record in self:
            name = f"[{record.provider}] {record.name}"
            result.append((record.id, name))
        return result


class OpenAISupport(models.Model):
    _name = "learning_japanese.openai_support"
    _description = "LLM Support"
    _order = "id desc"

    prompt_request_id = fields.Many2one(
        comodel_name="learning_japanese.prompt_request",
        string="Prompt Request",
        # auto_join=True,
    )
    request_name = fields.Text(string="Request Name", copy=False)
    content = fields.Text(string="Content", copy=False)
    response = fields.Html(string="Response", copy=False)
    is_send_request = fields.Boolean(string="Send Request?")
    llm_id = fields.Many2one(
        comodel_name="learning_japanese.llm_config",
        string="LLM Model",
        domain=[('is_active', '=', True)],
        required=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_send_request"):
                prompt_req_id = vals.get("prompt_request_id")
                content = vals.get("content")
                llm_config_id = vals.get("llm_id")

                if prompt_req_id and content and llm_config_id:
                    prompt_request = self.env["learning_japanese.prompt_request"].browse(prompt_req_id)
                    llm_config = self.env["learning_japanese.llm_config"].browse(llm_config_id)

                    # Pass the whole config object to the generator
                    result = self.generate_response(
                        prompt_request=prompt_request.content,
                        content=content,
                        llm_config=llm_config
                    )
                    vals["response"] = self.format_response_content(result)
        return super().create(vals_list)

    def generate_response(self, prompt_request, content, llm_config):
        """Dispatcher now uses the llm_config record"""
        if llm_config.provider == 'openAI':
            return self._generate_openai(prompt_request, content, llm_config.model_code)
        elif llm_config.provider == 'gemini':
            return self._generate_gemini(prompt_request, content, llm_config.model_code)
        raise UserError("Unsupported LLM provider.")

    def _generate_openai(self, prompt_request, content, model_name):
        api_key = self.env["ir.config_parameter"].sudo().get_param("openai.api_key")
        client = openai.OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model_name, # Use the dynamic model name from config
                messages=[{"role": "user", "content": self.create_prompt(prompt_request, content)}],
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise AccessError(f"OpenAI Error: {e}")

    def _generate_gemini(self, prompt_request, content, model_name):
        api_key = self.env["ir.config_parameter"].sudo().get_param("gemini.api_key")
        client = genai.Client(api_key=api_key)
        try:
            response = client.models.generate_content(
                model=model_name, # Use the dynamic model name from config
                contents=self.create_prompt(prompt_request, content),
            )
            return response.text or ""
        except Exception as e:
            raise AccessError(f"Gemini Error: {e}")

    @staticmethod
    def create_prompt(prompt_request: str, content: str) -> str:
        return f"""
        {prompt_request}
        Below is the content:
        {content}
        """

    def format_response_content(self, raw_content: str) -> str:
        """
        Aligns with vocabulary.py logic:
        1. Escapes HTML to protect << >> markers
        2. Adds <br/> after Japanese periods
        """
        if not raw_content:
            return ""

        # 1. Manually escape ONLY the Kanji markers so <p> tags remain valid
        formatted = raw_content.replace('<<', '&lt;&lt;').replace('>>', '&gt;&gt;')

        # 2. Add <br/> before the Vietnamese translation start
        formatted = re.sub(r'\{\{', r'<br/>{{', formatted)

        # 3. Add <br/> after '}}' ONLY if it is NOT the end of the string
        # (?!$) is a negative lookahead that means "not followed by the end of the string"
        formatted = re.sub(r'\}\}(?!$)', r'}}</br>', formatted)

        return formatted
