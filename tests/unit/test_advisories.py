"""Tests for the discouraged-import advisories (pandas -> polars)."""

from __future__ import annotations

import warnings

from tempestroid.cli.advisories import (
    DiscouragedImportWarning,
    advisories_for_source,
    scan_imported_roots,
    warn_discouraged_imports,
)


def test_scan_finds_top_level_import() -> None:
    """`import pandas` is reduced to the `pandas` root."""
    assert "pandas" in scan_imported_roots("import pandas")


def test_scan_finds_aliased_and_submodule_imports() -> None:
    """`import pandas as pd` and `from pandas.api import X` both yield `pandas`."""
    assert "pandas" in scan_imported_roots("import pandas as pd")
    assert "pandas" in scan_imported_roots(
        "from pandas.api.types import is_numeric_dtype"
    )


def test_scan_finds_nested_import() -> None:
    """An import inside a function body is still detected (apps lazy-import)."""
    source = "def view(app):\n    import pandas as pd\n    return pd"
    assert "pandas" in scan_imported_roots(source)


def test_scan_ignores_relative_imports() -> None:
    """Relative imports target the app's own package, never a discouraged dep."""
    assert scan_imported_roots("from . import pandas") == set()
    assert scan_imported_roots("from .pandas import thing") == set()


def test_scan_survives_syntax_error() -> None:
    """A non-parsing source yields no roots (the real exec surfaces the error)."""
    assert scan_imported_roots("def view(app)\n    return None") == set()


def test_advisory_for_pandas() -> None:
    """A pandas import produces exactly one advisory mentioning polars."""
    messages = advisories_for_source("import pandas")
    assert len(messages) == 1
    assert "polars" in messages[0]


def test_no_advisory_for_polars_or_numpy() -> None:
    """The recommended/neutral deps raise no advisory."""
    assert advisories_for_source("import polars as pl\nimport numpy as np") == []


def test_warn_emits_discouraged_import_warning() -> None:
    """`warn_discouraged_imports` raises a `DiscouragedImportWarning` for pandas."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        returned = warn_discouraged_imports("import pandas", filename="app.py")
    assert returned and "polars" in returned[0]
    assert len(caught) == 1
    assert issubclass(caught[0].category, DiscouragedImportWarning)
    assert "app.py" in str(caught[0].message)


def test_warn_silent_without_discouraged_import() -> None:
    """No warning is raised for a clean app source."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_discouraged_imports("import polars as pl", filename="app.py")
    assert caught == []


def test_spec_from_source_warns_on_pandas() -> None:
    """Loading an app whose source imports pandas surfaces the advisory.

    Proves the nudge reaches both the Qt sim and the device code-push path, which
    both funnel through `spec_from_source`.
    """
    from tempestroid.cli.app_loader import spec_from_source

    # pandas is imported inside an UNCALLED function: the AST scan still detects
    # it (it walks nested imports), so the advisory fires — but the exec never
    # runs the import, so the test does NOT require pandas to be installed (it
    # isn't — pandas is the discouraged dep this whole feature steers away from).
    source = (
        "def _uses_pandas():\n    import pandas  # noqa: F401\n"
        "def make_state():\n    return 0\n"
        "def view(app):\n"
        "    from tempestroid import Text\n"
        "    return Text(content='x')\n"
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spec_from_source(source, filename="myapp.py", name="_advisory_test_app")
    assert any(
        issubclass(w.category, DiscouragedImportWarning) and "polars" in str(w.message)
        for w in caught
    )
