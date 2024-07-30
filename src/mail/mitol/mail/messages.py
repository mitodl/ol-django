"""Mail messages"""

from typing import Tuple

from anymail.message import AnymailMessage
from django.conf import settings


class TemplatedMessage(AnymailMessage):
    """An email based off templates"""

    template_name: str
    name: str

    @staticmethod
    def get_base_template_context() -> dict:
        """Returns a dict of context variables that are needed in all emails"""  # noqa: D401
        return {
            "base_url": settings.SITE_BASE_URL,
            "site_name": settings.SITE_NAME,
        }

    @staticmethod
    def get_debug_template_context() -> dict:
        """Returns the extra context for the email debugger"""  # noqa: D401
        return {}

    @staticmethod
    def get_default_headers() -> dict:
        """The message's default headers"""  # noqa: D401
        return {"Reply-To": settings.MITOL_MAIL_REPLY_TO_ADDRESS}

    @classmethod
    def render_templates(cls, template_context: dict) -> Tuple[str, str, str]:  # noqa: FA100
        """
        Render the email's templates
        """
        # avoid circular import issue
        from mitol.mail import api

        return api.render_email_templates(cls.template_name, template_context)

    @classmethod
    def create(cls, **kwargs) -> "TemplatedMessage":
        """Factory method for an instance of this message, rendering the template to html and plaintext"""  # noqa: E501, D401

        if not getattr(cls, "template_name", None):
            raise ValueError(f"{cls.__name__}.template_name not defined")  # noqa: EM102, TRY003

        if not getattr(cls, "name", None):
            raise ValueError(f"{cls.__name__}.name not defined")  # noqa: EM102, TRY003

        from_email = kwargs.pop("from_email", settings.MITOL_MAIL_FROM_EMAIL)
        headers = {**cls.get_default_headers(), **kwargs.pop("headers", {})}

        template_context = {
            **cls.get_base_template_context(),
            **kwargs.pop("template_context", {}),
        }
        subject, text_body, html_body = cls.render_templates(template_context)
        alternatives = [(html_body, "text/html")]

        return cls(
            headers=headers,
            from_email=from_email,
            subject=subject,
            body=text_body,
            alternatives=alternatives,
            **kwargs,
        )

    @classmethod
    def debug(cls) -> "TemplatedMessage":
        """Get an instance of the message with debug data"""
        return cls.create(template_context=cls.get_debug_template_context())
