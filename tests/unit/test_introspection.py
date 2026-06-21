import json

from tempestroid import event_catalog, introspect, widget_catalog


def test_widget_catalog_lists_all_widgets():
    catalog = widget_catalog()
    assert set(catalog) == {
        "Text",
        "Button",
        "IconButton",
        "Column",
        "Row",
        "Container",
        "ScrollView",
        "Animated",
        "AnimatedList",
        "Hero",
        "Shimmer",
        "Skeleton",
        "Input",
        "TextArea",
        "Checkbox",
        "Switch",
        "Slider",
        "DatePicker",
        "FilePicker",
        "Dropdown",
        "TimePicker",
        "RangeSlider",
        "Autocomplete",
        "PinInput",
        "MaskedInput",
        "Form",
        "FormField",
        "Image",
        "Icon",
        "ProgressBar",
        "Spinner",
        "Stack",
        "Spacer",
        "Wrap",
        "PageView",
        "AspectRatio",
        "GestureDetector",
        "PanHandler",
        "ScaleHandler",
        "DoubleTapHandler",
        "Draggable",
        "DragTarget",
        "Dismissible",
        "ReorderableList",
        "InteractiveViewer",
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
        "Canvas",
        "VideoPlayer",
        "WebView",
        "Svg",
        "CameraPreview",
        "QrScanner",
        "MapView",
        "Blur",
        "BackdropFilter",
        "ClipPath",
        "KeyboardAvoidingView",
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
        "PanEvent",
        "ScaleEvent",
        "DragEvent",
        "ReorderEvent",
        "SelectEvent",
        "TimeChangeEvent",
        "RangeChangeEvent",
        "SubmitEvent",
        "ValidationEvent",
        "PageChangeEvent",
        "QrScanEvent",
        "LifecycleEvent",
        "SensorEvent",
        "ConnectivityEvent",
        "DeepLinkEvent",
        "ThemeChangeEvent",
        "LocaleChangeEvent",
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


# --- E3 animation widget catalog (phase E3) ----------------------------------


def test_animation_widgets_appear_in_catalog():
    """The five E3 animation widgets are introspected with prop schemas.

    Regression: ``Animated``/``AnimatedList``/``Hero``/``Shimmer``/``Skeleton``
    were initially absent from ``WIDGET_TYPES`` so ``tempest spec`` did not list
    them. They are handler-free, so their ``events`` map is empty.
    """
    catalog = widget_catalog()
    for name in ("Animated", "AnimatedList", "Hero", "Shimmer", "Skeleton"):
        assert name in catalog, f"{name} missing from widget catalog"
        assert "properties" in catalog[name]["schema"]
        assert catalog[name]["events"] == {}


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


# --- E9: semantics/focusable on the widget base + new context events --------


def test_semantics_and_focusable_in_widget_schema():
    """Every widget schema exposes the E9 base fields semantics/focusable."""
    catalog = widget_catalog()
    for name in ("Text", "Button", "Column"):
        props = catalog[name]["schema"]["properties"]
        assert "semantics" in props, f"{name} schema missing 'semantics'"
        assert "focusable" in props, f"{name} schema missing 'focusable'"
        assert "focus_order" in props, f"{name} schema missing 'focus_order'"


def test_theme_and_locale_events_in_event_catalog():
    """ThemeChangeEvent and LocaleChangeEvent appear in the event catalog."""
    catalog = event_catalog()
    assert "ThemeChangeEvent" in catalog
    assert "LocaleChangeEvent" in catalog
    assert "mode" in catalog["ThemeChangeEvent"]["properties"]
    locale_props = catalog["LocaleChangeEvent"]["properties"]
    assert "language" in locale_props
    assert "rtl" in locale_props


def test_introspect_is_json_serializable_with_e9():
    """The full contract — including the E9 surface — stays JSON-serializable."""
    blob = json.dumps(introspect())
    assert "ThemeChangeEvent" in blob
    assert "LocaleChangeEvent" in blob
    assert "semantics" in blob
