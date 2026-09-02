from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model

from .models import BugReport


class BugReportForm(forms.ModelForm):
    class Meta:
        model = BugReport
        fields = [
            "screen", "screen_path", "title", "priority", "status", "description",
            "current_result", "expected_result", "reproduction_steps", "attachment",
            "browser_info", "assigned_to", "technical_notes", "root_cause", "resolution_notes", "fixed_version", "retest_notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "current_result": forms.Textarea(attrs={"rows": 4}),
            "expected_result": forms.Textarea(attrs={"rows": 4}),
            "reproduction_steps": forms.Textarea(attrs={"rows": 5, "placeholder": "1. ...\n2. ...\n3. ..."}),
            "technical_notes": forms.Textarea(attrs={"rows": 4}),
            "root_cause": forms.Textarea(attrs={"rows": 4, "placeholder": "Preencher após investigação/reprodução."}),
            "resolution_notes": forms.Textarea(attrs={"rows": 4}),
            "retest_notes": forms.Textarea(attrs={"rows": 4}),
            "screen_path": forms.TextInput(attrs={"placeholder": "/operacao/hoje/"}),
            "browser_info": forms.TextInput(attrs={"placeholder": "Ex.: Chrome 152 / Windows 11"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["assigned_to"].required = False
        self.fields["screen_path"].required = False
        self.fields["attachment"].required = False
        for field in self.fields.values():
            css = "form-control"
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (current + " " + css).strip()

    def clean_attachment(self):
        file = self.cleaned_data.get("attachment")
        if file and file.size > 8 * 1024 * 1024:
            raise forms.ValidationError("O anexo deve ter no máximo 8 MB.")
        return file
