import pytest

from aistudio_api.domain.model_capabilities import (
    get_model_metadata,
    plan_image_generation,
    validate_chat_capabilities,
)


def test_model_metadata_exposes_capabilities_and_image_sizes():
    metadata = get_model_metadata("gemini-3.1-flash-image-preview")

    assert metadata["capabilities"]["image_output"] is True
    assert metadata["capabilities"]["structured_output"] is False
    assert metadata["capabilities"]["tool_calls"] is False
    assert "media_resolution" in metadata["capabilities"]["unsupported_generation_fields"]
    assert "media_resolution" in metadata["unsupported_generation_fields"]
    assert metadata["image_generation"]["response_formats"] == ["b64_json", "url"]
    assert {item["size"] for item in metadata["image_generation"]["sizes"]} >= {
        "1024x1024",
        "1024x1792",
        "1792x1024",
    }


def test_chat_capability_validation_rejects_image_input_for_gemma():
    with pytest.raises(ValueError, match="image input"):
        validate_chat_capabilities(
            "gemma-4-31b-it",
            has_image_input=True,
            uses_tools=False,
            uses_search=False,
            uses_thinking=False,
            stream=False,
        )


def test_model_metadata_exposes_structured_output_for_text_model():
    metadata = get_model_metadata("gemini-3-flash-preview")

    assert metadata["capabilities"]["text_output"] is True
    assert metadata["capabilities"]["structured_output"] is True
    assert metadata["capabilities"]["tool_calls"] is True


def test_chat_capability_validation_rejects_structured_output_when_unavailable():
    with pytest.raises(ValueError, match="structured output"):
        validate_chat_capabilities(
            "gemini-3.1-flash-tts-preview",
            has_image_input=False,
            uses_tools=False,
            uses_search=False,
            uses_thinking=False,
            stream=False,
            uses_structured_output=True,
        )


@pytest.mark.parametrize(
    ("size", "output_image_size"),
    [
        ("512x512", "512"),
        ("1024x1024", "1K"),
        ("1024x1792", "1K"),
        ("1792x1024", "1K"),
    ],
)
def test_image_generation_plan_maps_supported_size_to_wire_config(size, output_image_size):
    plan = plan_image_generation("models/gemini-3.1-flash-image-preview", size)

    assert plan.model == "gemini-3.1-flash-image-preview"
    assert plan.generation_config_overrides == {"output_image_size": [None, output_image_size]}


def test_image_generation_plan_rejects_unsupported_size():
    with pytest.raises(ValueError, match="Supported sizes"):
        plan_image_generation("gemini-3.1-flash-image-preview", "256x256")