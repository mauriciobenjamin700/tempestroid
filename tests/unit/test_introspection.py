import json

from tempestroid import event_catalog, introspect, widget_catalog


def test_widget_catalog_lists_all_widgets():
    catalog = widget_catalog()
    assert set(catalog) == {"Text", "Button", "Column", "Row", "Container"}


def test_text_schema_exposes_content_field():
    catalog = widget_catalog()
    properties = catalog["Text"]["schema"]["properties"]
    assert "content" in properties


def test_button_publishes_its_event_contract():
    catalog = widget_catalog()
    assert catalog["Button"]["events"] == {"on_click": "TapEvent"}


def test_button_schema_handles_handler_field():
    # The handler field must not crash JSON-schema generation.
    schema = widget_catalog()["Button"]["schema"]
    assert "on_click" in schema["properties"]


def test_event_catalog_lists_events():
    catalog = event_catalog()
    assert set(catalog) == {"TapEvent", "TextChangeEvent"}
    assert "value" in catalog["TextChangeEvent"]["properties"]


def test_introspect_is_json_serializable():
    spec = introspect()
    dumped = json.dumps(spec)  # must not raise
    assert "widgets" in json.loads(dumped)
    assert "events" in spec
