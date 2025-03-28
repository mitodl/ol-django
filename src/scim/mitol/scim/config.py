from django_scim.models import SCIMServiceProviderConfig


class LearnSCIMServiceProviderConfig(SCIMServiceProviderConfig):
    """Custom provider config"""

    def to_dict(self):
        result = super().to_dict()

        result["bulk"]["supported"] = True
        result["filter"]["supported"] = True

        return result
