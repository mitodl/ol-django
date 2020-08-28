"""Mail views"""
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from mitol.mail.api import get_message_classes
from mitol.mail.forms import EmailDebuggerForm


@method_decorator(csrf_exempt, name="dispatch")
class EmailDebuggerView(View):
    """Email debugger view"""

    form_cls = EmailDebuggerForm
    template_name = "mail/email_debugger.html"

    def get(self, request):
        """Displays the debugger UI"""
        form = self.form_cls(initial={})
        return render(request, self.template_name, {"form": form})

    def post(self, request):  # pragma: no cover
        """Renders a test email"""
        form = self.form_cls(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        template_name = form.cleaned_data["template_name"]

        # if the form was valid, this should match on a message class
        for message_cls in get_message_classes():
            if message_cls.template_name == template_name:
                instance = message_cls.debug()

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "subject": instance.subject,
                "html_body": instance.alternatives[0][0],
                "text_body": instance.body,
            },
        )
