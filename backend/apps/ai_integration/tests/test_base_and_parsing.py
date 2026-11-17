import pytest

from apps.ai_integration.base import DiagnosisResult
from apps.ai_integration.errors import ProviderBadResponse
from apps.ai_integration.parsing import extract_json_object

VALID = {
    "health_status": "unhealthy", "confidence": 0.9, "common_name": "Early blight",
    "scientific_name": "Alternaria solani", "pathogen_type": "fungal",
    "symptoms": ["Brown rings"], "organic_treatment": ["Prune"],
    "chemical_treatment": ["Fungicide per label"], "prevention": ["Rotate crops"],
}


def test_valid_result_round_trips():
    result = DiagnosisResult.from_dict(VALID)
    assert result.to_dict() == VALID


def test_confidence_given_as_percentage_is_scaled():
    assert DiagnosisResult.from_dict({**VALID, "confidence": 87}).confidence == 0.87


def test_unexpected_enum_value_is_rejected():
    with pytest.raises(ProviderBadResponse):
        DiagnosisResult.from_dict({**VALID, "pathogen_type": "gremlins"})


def test_missing_required_field_is_rejected():
    data = dict(VALID)
    del data["health_status"]
    with pytest.raises(ProviderBadResponse):
        DiagnosisResult.from_dict(data)


def test_aliases_are_normalized():
    result = DiagnosisResult.from_dict({**VALID, "pathogen_type": "Fungus", "health_status": " Diseased "})
    assert result.pathogen_type == "fungal"
    assert result.health_status == "unhealthy"


def test_healthy_always_has_pathogen_none():
    result = DiagnosisResult.from_dict({**VALID, "health_status": "healthy", "pathogen_type": "fungal"})
    assert result.pathogen_type == "none"


def test_lists_are_cleaned_and_capped():
    result = DiagnosisResult.from_dict({**VALID, "symptoms": "single string", "prevention": [f"tip {i}" for i in range(30)]})
    assert result.symptoms == ["single string"]
    assert len(result.prevention) == 10


def test_non_list_value_is_rejected():
    with pytest.raises(ProviderBadResponse):
        DiagnosisResult.from_dict({**VALID, "symptoms": {"a": 1}})


def test_extract_plain_json():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_inside_code_fence():
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_surrounded_by_prose():
    assert extract_json_object('Sure! Here is the result: {"a": {"b": 2}} Hope this helps.') == {"a": {"b": 2}}


@pytest.mark.parametrize("bad", ["", "   ", "no json here", '{"a": ', "[1, 2, 3]"])
def test_extract_rejects_garbage(bad):
    with pytest.raises(ProviderBadResponse):
        extract_json_object(bad)