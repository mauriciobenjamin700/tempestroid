"""UI tests for the forms example, driven by the F9 native test driver.

Run them in the headless backend (no Qt, no device) with::

    uv run tempest uitest examples/forms/test_forms.py

A UI test file is an ordinary app module — it re-uses ``view`` and ``make_state``
from the sibling ``app.py`` — plus ``async def test_*(page)`` functions. Each test
gets a fresh :class:`Page` over a fresh in-process app; every action and assertion
auto-waits for the tree to settle (no ``sleep`` calls, no flake).

The form's validation runs purely in Python and folds back into the tree as the
``FormField.error`` **prop** (the renderers draw it imperatively, so it is not a
visible Text node) — assert it with ``get_by_prop``. The ``summary`` Text *is* a
node, so its "Submitted!" / prompt state is asserted with ``expect_text``. Because
the driver speaks the renderer-agnostic IR + typed events, this same script also
runs on the emulator/device (``--target emulator``).
"""

from __future__ import annotations

# Re-export the full app contract — including ``make_theme`` so the served module
# carries the app's initial theme (dark). The driver loads THIS module as the app,
# so without re-exporting ``make_theme`` the theme would silently fall back to
# ``system`` and the device render would not match ``examples/forms/app.py``.
from app import make_state, make_theme, view  # noqa: F401 — the app contract

from tempestroid.testing import Page

__all__ = ["make_state", "make_theme", "view"]

_PROMPT = "Fill the form and submit (invalid fields block it)."
_EMAIL_ERROR = "E-mail inválido"
_NAME_ERROR = "Campo obrigatório"


async def test_starts_with_the_prompt_and_no_errors(page: Page) -> None:
    """The form opens on the prompt with neither field carrying an error."""
    await page.expect_text("Create account")
    await page.expect_text(_PROMPT)
    await page.expect_count(page.get_by_prop("error", _EMAIL_ERROR), 0)


async def test_submit_invalid_blocks_and_shows_field_errors(page: Page) -> None:
    """Submitting a bad e-mail + empty name blocks submit and flags both fields."""
    await page.fill(page.get_by_key("email-input"), "not-an-email")
    await page.submit(page.get_by_key("signup-form"))
    # Validation folds the per-field errors back as the FormField ``error`` prop.
    await page.expect_visible(page.get_by_prop("error", _EMAIL_ERROR))
    await page.expect_visible(page.get_by_prop("error", _NAME_ERROR))
    # Submit stays gated: the summary keeps the prompt, not "Submitted!".
    await page.expect_text(_PROMPT)


async def test_submit_valid_marks_submitted(page: Page) -> None:
    """Filling a valid e-mail and name then submitting flips the summary."""
    await page.fill(page.get_by_key("email-input"), "ana@example.com")
    await page.fill(page.get_by_key("name-input"), "Ana")
    await page.submit(page.get_by_key("signup-form"))
    await page.expect_text("Submitted!")
    await page.expect_count(page.get_by_prop("error", _EMAIL_ERROR), 0)
