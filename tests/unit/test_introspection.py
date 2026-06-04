import json

from tempestroid import event_catalog, introspect, widget_catalog


def test_widget_catalog_lists_all_widgets():
    catalog = widget_catalog()
    assert set(catalog) == {
        "Text",
        "Button",
        "Column",
        "Row",
        "Container",
        "ScrollView",
        "Input",
        "TextArea",
        "Checkbox",
        "Switch",
        "Slider",
        "DatePicker",
        "FilePicker",
        "Image",
        "Icon",
        "ProgressBar",
        "Spinner",
        "Stack",
        "GestureDetector",
        "Navigator",
        "TabView",
        "TabBar",
        "RouteDrawer",
        "LazyColumn",
        "LazyRow",
        "LazyGrid",
        "SectionList",
        "RefreshControl",
        "Dialog",
        "BottomSheet",
        "Toast",
        "Tooltip",
        "Menu",
        "Popover",
        "ActionSheet",
    }


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
    assert set(catalog) == {
        "TapEvent",
        "TextChangeEvent",
        "ToggleEvent",
        "SlideEvent",
        "DateChangeEvent",
        "FileSelectEvent",
        "LongPressEvent",
        "SwipeEvent",
        "RouteChangeEvent",
        "ScrollEvent",
        "RefreshEvent",
        "EndReachedEvent",
        "DismissEvent",
        "MenuSelectEvent",
    }
    assert "value" in catalog["TextChangeEvent"]["properties"]


def test_input_publishes_its_event_contract():
    catalog = widget_catalog()
    assert catalog["Input"]["events"] == {"on_change": "TextChangeEvent"}
    assert catalog["Checkbox"]["events"] == {"on_change": "ToggleEvent"}
    assert catalog["DatePicker"]["events"] == {"on_change": "DateChangeEvent"}
    assert catalog["FilePicker"]["events"] == {"on_select": "FileSelectEvent"}


def test_introspect_is_json_serializable():
    spec = introspect()
    dumped = json.dumps(spec)  # must not raise
    assert "widgets" in json.loads(dumped)
    assert "events" in spec


# --- E2 overlay widget event contracts (phase E2) ----------------------------


def test_dialog_publishes_on_dismiss_event():
    """Dialog.event_schemas maps on_dismiss → DismissEvent in the widget catalog."""
    catalog = widget_catalog()
    assert catalog["Dialog"]["events"] == {"on_dismiss": "DismissEvent"}


def test_bottom_sheet_publishes_on_dismiss_event():
    """BottomSheet.event_schemas maps on_dismiss → DismissEvent."""
    catalog = widget_catalog()
    assert catalog["BottomSheet"]["events"] == {"on_dismiss": "DismissEvent"}


def test_popover_publishes_on_dismiss_event():
    """Popover.event_schemas maps on_dismiss → DismissEvent."""
    catalog = widget_catalog()
    assert catalog["Popover"]["events"] == {"on_dismiss": "DismissEvent"}


def test_menu_publishes_on_select_event():
    """Menu.event_schemas maps on_select → MenuSelectEvent in the widget catalog."""
    catalog = widget_catalog()
    assert catalog["Menu"]["events"] == {"on_select": "MenuSelectEvent"}


def test_action_sheet_publishes_on_select_event():
    """ActionSheet.event_schemas maps on_select → MenuSelectEvent."""
    catalog = widget_catalog()
    assert catalog["ActionSheet"]["events"] == {"on_select": "MenuSelectEvent"}


def test_toast_and_tooltip_have_no_events():
    """Toast and Tooltip declare no event handlers (event_schemas is empty)."""
    catalog = widget_catalog()
    assert catalog["Toast"]["events"] == {}
    assert catalog["Tooltip"]["events"] == {}


def test_dismiss_event_schema_carries_overlay_id_field():
    """DismissEvent schema exposes the overlay_id field for introspection."""
    catalog = event_catalog()
    props = catalog["DismissEvent"]["properties"]
    assert "overlay_id" in props


def test_menu_select_event_schema_carries_value_and_label():
    """MenuSelectEvent schema exposes both value and label fields."""
    catalog = event_catalog()
    props = catalog["MenuSelectEvent"]["properties"]
    assert "value" in props
    assert "label" in props
