import pytest
from pydantic import ValidationError

from tools import AnimalData


def make_animal(**overrides) -> AnimalData:
    fields = {"id": 1, "name": "Red Fox", "text": "A small omnivore.", "distance": 0.25}
    return AnimalData(**{**fields, **overrides})


def test_valid_fields_are_stored():
    animal = make_animal()

    assert animal.id == 1
    assert animal.name == "Red Fox"
    assert animal.text == "A small omnivore."
    assert animal.distance == 0.25


@pytest.mark.parametrize("field", ["id", "name", "text", "distance"])
def test_missing_field_is_rejected(field):
    fields = make_animal().model_dump()
    del fields[field]

    with pytest.raises(ValidationError) as exc_info:
        AnimalData(**fields)

    error = exc_info.value.errors()[0]
    assert error["type"] == "missing"
    assert error["loc"] == (field,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "not-a-number"),
        ("name", 123),
        ("text", None),
        ("distance", "far"),
    ],
)
def test_invalid_field_type_is_rejected(field, value):
    with pytest.raises(ValidationError) as exc_info:
        make_animal(**{field: value})

    assert exc_info.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("length", [0, 1, 39, 40])
def test_repr_keeps_text_of_40_characters_or_fewer(length):
    text = "x" * length

    assert f"text={text!r}" in repr(make_animal(text=text))


@pytest.mark.parametrize("length", [41, 500])
def test_repr_truncates_text_longer_than_40_characters(length):
    expected = "x" * 40 + "..."

    assert f"text={expected!r}" in repr(make_animal(text="x" * length))


def test_repr_includes_all_fields():
    animal = make_animal(id=7, name="Lynx", text="Short text", distance=0.5)

    assert repr(animal) == (
        "AnimalData(id=7, name='Lynx', text='Short text', distance=0.5)"
    )


def test_repr_truncation_does_not_change_stored_text():
    text = "x" * 100
    animal = make_animal(text=text)

    repr(animal)

    assert animal.text == text
    assert animal.model_dump()["text"] == text
