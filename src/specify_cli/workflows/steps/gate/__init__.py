"""Gate step — human review gate."""

from __future__ import annotations

import sys
from pathlib import Path
import re
from typing import Any

from specify_cli.workflows.base import StepBase, StepContext, StepResult, StepStatus
from specify_cli.workflows.expressions import evaluate_expression


class GateStep(StepBase):
    """Interactive review gate.

    When running in an interactive terminal, prompts the user to choose
    an option (e.g. approve / reject).  Falls back to ``PAUSED`` when
    stdin is not a TTY (CI, piped input) so the run can be resumed
    later with ``specify workflow resume``.

    The user's choice is stored in ``output.choice``.  ``on_reject``
    controls abort / skip behaviour.
    """

    type_key = "gate"
    _MAX_FILE_LINES = 200
    _CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

    def execute(self, config: dict[str, Any], context: StepContext) -> StepResult:
        message = config.get("message", "Review required.")
        if isinstance(message, str) and "{{" in message:
            message = evaluate_expression(message, context)

        options = config.get("options", ["approve", "reject"])
        on_reject = config.get("on_reject", "abort")

        show_file = config.get("show_file")
        if show_file and isinstance(show_file, str) and "{{" in show_file:
            show_file = evaluate_expression(show_file, context)

        output = {
            "message": message,
            "options": options,
            "on_reject": on_reject,
            "show_file": show_file,
            "choice": None,
        }

        if show_file:
            rendered, display_error = self._read_show_file(show_file, context)
            output["show_file_content"] = rendered
            if display_error:
                output["show_file_error"] = display_error

        # Non-interactive: pause for later resume
        if not sys.stdin.isatty():
            return StepResult(status=StepStatus.PAUSED, output=output)

        # Interactive: prompt the user
        choice = self._prompt(message, options, output.get("show_file_content"))
        output["choice"] = choice

        if choice.lower() in ("reject", "abort"):
            if on_reject == "abort":
                output["aborted"] = True
                return StepResult(
                    status=StepStatus.FAILED,
                    output=output,
                    error=f"Gate rejected by user at step {config.get('id', '?')!r}",
                )
            if on_reject == "retry":
                # Pause so the next resume re-executes this gate
                return StepResult(status=StepStatus.PAUSED, output=output)
            # on_reject == "skip" → completed, downstream steps decide
            return StepResult(status=StepStatus.COMPLETED, output=output)

        return StepResult(status=StepStatus.COMPLETED, output=output)

    @staticmethod
    def _prompt(
        message: str, options: list[str], show_file_content: str | None = None
    ) -> str:
        """Display gate message and prompt for a choice."""
        print("\n  +-- Gate ------------------------------------")
        print(f"  | {message}")
        if show_file_content:
            print("  |")
            for line in show_file_content.splitlines():
                print(f"  | {line}")
        print("  |")
        for i, opt in enumerate(options, 1):
            print(f"  |  [{i}] {opt}")
        print("  +--------------------------------------------")

        while True:
            try:
                raw = input(f"  Choose [1-{len(options)}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return options[-1]  # default to last (usually reject)
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            # Also accept the option name directly
            if raw.lower() in [o.lower() for o in options]:
                return next(o for o in options if o.lower() == raw.lower())
            print(f"  Invalid choice. Enter 1-{len(options)} or an option name.")

    @classmethod
    def _read_show_file(
        cls, show_file: Any, context: StepContext
    ) -> tuple[str, str | None]:
        if not isinstance(show_file, str) or not show_file.strip():
            return "", "show_file must resolve to a non-empty path string."
        path = Path(show_file).expanduser()
        if not path.is_absolute():
            path = Path(context.project_root or ".") / path
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            return "", f"Unable to read gate show_file {path}: {exc}"
        bounded = lines[: cls._MAX_FILE_LINES]
        rendered = "\n".join(cls._CONTROL_CHARS.sub("", line) for line in bounded)
        if len(lines) > cls._MAX_FILE_LINES:
            rendered += f"\n... truncated after {cls._MAX_FILE_LINES} lines ..."
        return rendered, None

    def validate(self, config: dict[str, Any]) -> list[str]:
        errors = super().validate(config)
        if "message" not in config:
            errors.append(
                f"Gate step {config.get('id', '?')!r} is missing 'message' field."
            )
        elif not isinstance(config["message"], str):
            errors.append(
                f"Gate step {config.get('id', '?')!r}: 'message' must be a string."
            )
        options = config.get("options", ["approve", "reject"])
        if not isinstance(options, list) or not options:
            errors.append(
                f"Gate step {config.get('id', '?')!r}: 'options' must be a non-empty list."
            )
        elif not all(isinstance(o, str) for o in options):
            errors.append(
                f"Gate step {config.get('id', '?')!r}: all options must be strings."
            )
        on_reject = config.get("on_reject", "abort")
        if on_reject not in ("abort", "skip", "retry"):
            errors.append(
                f"Gate step {config.get('id', '?')!r}: 'on_reject' must be "
                f"'abort', 'skip', or 'retry'."
            )
        if (
            on_reject in ("abort", "retry")
            and isinstance(options, list)
            and all(isinstance(o, str) for o in options)
        ):
            reject_choices = {"reject", "abort"}
            if not any(o.lower() in reject_choices for o in options):
                errors.append(
                    f"Gate step {config.get('id', '?')!r}: on_reject={on_reject!r} "
                    f"but options has no 'reject' or 'abort' choice."
                )
        if "show_file" in config and not isinstance(config["show_file"], str):
            errors.append(
                f"Gate step {config.get('id', '?')!r}: 'show_file' must be a string."
            )
        return errors
