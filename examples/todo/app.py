"""Tap-driven todo list — gallery example.

No text input widget exists yet, so tasks are added from a fixed pool by tapping
"+ add"; tapping a task toggles done; "clear done" removes the completed ones.
This exercises every child patch the reconciler emits: ``insert`` (add),
``remove`` (clear), ``update`` (toggle label) and stable-key reordering.

Runs in the Qt simulator::

    uv run python examples/todo/app.py

and on a device via code-push (``make_state`` + ``view`` contract)::

    uv run tempest serve examples/todo/app.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestroid import (
    App,
    Button,
    Color,
    Column,
    Edge,
    FontWeight,
    Row,
    Style,
    Text,
    Widget,
)

_POOL: tuple[str, ...] = (
    "Buy milk",
    "Write tests",
    "Call dentist",
    "Ship release",
    "Water plants",
    "Read a book",
)


def _no_tasks() -> list[Task]:
    """Provide a typed empty task list for the default factory.

    Returns:
        A new empty list of tasks.
    """
    return []


@dataclass
class Task:
    """A single todo item.

    Attributes:
        id: A stable identifier used as the widget key.
        text: The task description.
        done: Whether the task is completed.
    """

    id: int
    text: str
    done: bool = False


@dataclass
class TodoState:
    """The todo list's mutable state.

    Attributes:
        tasks: The current tasks in display order.
        next_id: The id to assign to the next added task.
        pool_index: The next index into ``_POOL`` to add from.
    """

    tasks: list[Task] = field(default_factory=_no_tasks)
    next_id: int = 1
    pool_index: int = 0


def make_state() -> TodoState:
    """Build a fresh initial state with two seeded tasks.

    Returns:
        A new todo state.
    """
    return TodoState(
        tasks=[Task(id=1, text=_POOL[0]), Task(id=2, text=_POOL[1], done=True)],
        next_id=3,
        pool_index=2,
    )


def _add_task(state: TodoState) -> None:
    """Append the next task from the pool (cycling)."""
    text = _POOL[state.pool_index % len(_POOL)]
    state.tasks.append(Task(id=state.next_id, text=text))
    state.next_id += 1
    state.pool_index += 1


def _toggle(state: TodoState, task_id: int) -> None:
    """Flip the done flag of the task with the given id."""
    for task in state.tasks:
        if task.id == task_id:
            task.done = not task.done
            return


def _clear_done(state: TodoState) -> None:
    """Drop every completed task."""
    state.tasks = [task for task in state.tasks if not task.done]


def _task_row(app: App[TodoState], task: Task) -> Widget:
    """Build one tappable task row.

    Args:
        app: The running app.
        task: The task to render.

    Returns:
        A button whose label reflects the done state.
    """
    mark = "✓" if task.done else "○"
    color = Color.from_hex("#6b7280") if task.done else Color.from_hex("#e5e7eb")
    return Button(
        label=f"{mark}  {task.text}",
        on_click=lambda: app.set_state(lambda s: _toggle(s, task.id)),
        key=f"task-{task.id}",
        style=Style(
            padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
            radius=8.0,
            background=Color.from_hex("#1f2937"),
            color=color,
        ),
    )


def view(app: App[TodoState]) -> Widget:
    """Build the todo UI for the current state.

    Args:
        app: The running app (read ``app.state``, wire handlers to
            ``app.set_state``).

    Returns:
        The root widget of the todo screen.
    """
    remaining = sum(1 for task in app.state.tasks if not task.done)
    return Column(
        style=Style(
            gap=12.0,
            padding=Edge.all(24.0),
            background=Color.from_hex("#0b0f14"),
        ),
        children=[
            Text(
                content=f"Todo — {remaining} left",
                style=Style(
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#f9fafb"),
                ),
                key="title",
            ),
            Row(
                style=Style(gap=8.0),
                children=[
                    Button(
                        label="+ add",
                        on_click=lambda: app.set_state(_add_task),
                        key="add",
                        style=Style(
                            padding=Edge.symmetric(vertical=10.0, horizontal=16.0),
                            radius=8.0,
                            background=Color.from_hex("#2563eb"),
                            color=Color.from_hex("#ffffff"),
                        ),
                    ),
                    Button(
                        label="clear done",
                        on_click=lambda: app.set_state(_clear_done),
                        key="clear",
                        style=Style(
                            padding=Edge.symmetric(vertical=10.0, horizontal=16.0),
                            radius=8.0,
                            background=Color.from_hex("#374151"),
                            color=Color.from_hex("#f9fafb"),
                        ),
                    ),
                ],
            ),
            Column(
                style=Style(gap=8.0),
                children=[_task_row(app, task) for task in app.state.tasks],
                key="list",
            ),
        ],
    )


if __name__ == "__main__":
    from tempestroid.renderers.qt import run_qt

    raise SystemExit(
        run_qt(make_state(), view, title="tempestroid — todo", size=(360, 480))
    )
