"""Pydantic-MVP: gueltige und ungueltige Eingaben unterscheiden."""

from pydantic import ValidationError

from unterricht.demo_app import SearchRequest


def run() -> None:
    valid = SearchRequest.model_validate({"query": "OCR", "limit": 2})
    print(f"Pydantic: gültig -> {valid.model_dump()}")
    try:
        SearchRequest.model_validate({"query": "X", "limit": 99})
    except ValidationError as error:
        fields = sorted({".".join(map(str, item["loc"])) for item in error.errors()})
        print(f"Pydantic: ungültig erkannt -> {', '.join(fields)}")


if __name__ == "__main__":
    run()
