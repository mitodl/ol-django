from mitol.common.serializers import BaseSerializer

from main.models import FirstLevel1, FirstLevel2, SecondLevel1, SecondLevel2


class HasNoPrefetchesSerializer(BaseSerializer): ...


class SecondLevel1Serializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = SecondLevel1
        fields = ["id"]


class FirstLevel1Serializer(BaseSerializer):
    required_prefetches = ["second_level"]

    second_level = SecondLevel1Serializer()

    class Meta:
        model = FirstLevel1
        fields = ["id", "second_level"]


class SecondLevel2Serializer(BaseSerializer):
    required_prefetches = []

    class Meta:
        model = SecondLevel2
        fields = ["id"]


class FirstLevel2Serializer(BaseSerializer):
    required_prefetches = ["second_levels"]
    second_levels = SecondLevel2Serializer(many=True)

    class Meta:
        model = FirstLevel2
        fields = ["id", "second_levels"]
