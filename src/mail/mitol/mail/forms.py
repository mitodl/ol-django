"""Mail forms"""
from django import forms

from mitol.mail.api import get_message_classes


def _get_message_class_choices():
    """Get message class choices"""
    return [
        (message_cls.template_name, message_cls.name)
        for message_cls in get_message_classes()
    ]


class EmailDebuggerForm(forms.Form):
    """Form for email debugger"""

    template_name = forms.ChoiceField(
        choices=_get_message_class_choices,
        widget=forms.Select(attrs={"class": "form-control m-2"}),
    )
