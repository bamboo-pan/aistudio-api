"""Helpers for task-level fine-grained workflow state."""

from __future__ import annotations

import copy
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from .git import run_git
from .io import read_json, write_json
from .prd_status import can_enter_implementation, ensure_task_meta, get_prd_status


WORKFLOW_VERSION: Final[int] = 1

STEP_AWAITING_IMPLEMENT: Final[str] = "awaiting_implement"
STEP_AWAITING_CHECK: Final[str] = "awaiting_check"
STEP_AWAITING_SPEC_REVIEW: Final[str] = "awaiting_spec_review"
STEP_AWAITING_COMMIT: Final[str] = "awaiting_commit"
STEP_READY_TO_FINISH: Final[str] = "ready_to_finish"

WORKFLOW_STEPS: Final[tuple[str, ...]] = (
    STEP_AWAITING_IMPLEMENT,
    STEP_AWAITING_CHECK,
    STEP_AWAITING_SPEC_REVIEW,
    STEP_AWAITING_COMMIT,
    STEP_READY_TO_FINISH,
)
_CHECK_COMPLETED_STEPS: Final[tuple[str, ...]] = (
    STEP_AWAITING_CHECK,
    STEP_AWAITING_SPEC_REVIEW,
    STEP_AWAITING_COMMIT,
    STEP_READY_TO_FINISH,
)

EVENT_IMPLEMENT_DISPATCHED: Final[str] = "implement-dispatched"
EVENT_IMPLEMENT_COMPLETED: Final[str] = "implement-completed"
EVENT_CHECK_COMPLETED: Final[str] = "check-completed"
EVENT_SPEC_REVIEWED_UPDATED: Final[str] = "spec-reviewed-updated"
EVENT_SPEC_REVIEWED_NOOP: Final[str] = "spec-reviewed-noop"
EVENT_COMMIT_RECORDED: Final[str] = "commit-recorded"
EVENT_READY_TO_FINISH: Final[str] = "ready-to-finish"

WORKFLOW_EVENTS: Final[tuple[str, ...]] = (
    EVENT_IMPLEMENT_DISPATCHED,
    EVENT_IMPLEMENT_COMPLETED,
    EVENT_CHECK_COMPLETED,
    EVENT_SPEC_REVIEWED_UPDATED,
    EVENT_SPEC_REVIEWED_NOOP,
    EVENT_COMMIT_RECORDED,
    EVENT_READY_TO_FINISH,
)

ACTION_START: Final[str] = "start"
ACTION_DISPATCH_IMPLEMENT: Final[str] = "dispatch-implement"
ACTION_DISPATCH_CHECK: Final[str] = "dispatch-check"
ACTION_REVIEW_SPEC: Final[str] = "review-spec"
ACTION_COMMIT: Final[str] = "commit"
ACTION_FINISH: Final[str] = "finish"
ACTION_ARCHIVE: Final[str] = "archive"

WORKFLOW_ACTIONS: Final[tuple[str, ...]] = (
    ACTION_START,
    ACTION_DISPATCH_IMPLEMENT,
    ACTION_DISPATCH_CHECK,
    ACTION_REVIEW_SPEC,
    ACTION_COMMIT,
    ACTION_FINISH,
    ACTION_ARCHIVE,
)

VCS_GIT: Final[str] = "git"
VCS_NON_GIT: Final[str] = "non-git"

_NON_CODE_PREFIXES: Final[tuple[str, ...]] = (
    ".trellis/tasks",
    ".trellis/workspace",
    ".trellis/.runtime",
)
_GIT_EXCLUDED_PATHSPECS: Final[tuple[str, ...]] = (
    ":(exclude).trellis/tasks/**",
    ":(exclude).trellis/workspace/**",
    ":(exclude).trellis/.runtime/**",
)


class WorkflowError(Exception):
    """Raised when a workflow transition or persisted state operation fails."""


@dataclass(frozen=True)
class GuardResult:
    """Result returned by workflow guard checks."""

    allowed: bool
    message: str
    current_step: str


def utc_timestamp() -> str:
    """Return a compact UTC ISO timestamp for workflow audit fields."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def detect_vcs(repo_root: Path) -> dict:
    """Detect whether the project is currently inside a git work tree."""
    rc, out, _ = run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    if rc == 0 and out.strip().lower() == "true":
        return {"kind": VCS_GIT, "commit_required": True}
    return {"kind": VCS_NON_GIT, "commit_required": False}


def get_git_head(repo_root: Path) -> str | None:
    """Return the current git HEAD hash when available."""
    rc, out, _ = run_git(["rev-parse", "HEAD"], cwd=repo_root)
    if rc != 0:
        return None
    head = out.strip()
    return head or None


def default_workflow_state(repo_root: Path, current_step: str = STEP_AWAITING_IMPLEMENT) -> dict:
    """Build a fresh ``meta.workflow`` value."""
    vcs = detect_vcs(repo_root)
    return {
        "version": WORKFLOW_VERSION,
        "current_step": current_step,
        "vcs": vcs,
        "implement": {
            "dispatched_at": None,
            "completed_at": None,
        },
        "check": {
            "completed_at": None,
            "fingerprint": None,
            "head": None,
        },
        "spec_update": {
            "reviewed_at": None,
            "result": None,
        },
        "commit": {
            "hash": None,
            "recorded_at": None,
        },
    }


def ensure_workflow_state(
    task: dict,
    repo_root: Path,
    current_step: str | None = None,
) -> dict:
    """Return ``task['meta']['workflow']`` as a mutable dict with defaults.

    Unknown task fields, unknown ``meta`` fields, and unknown workflow subkeys are
    preserved. VCS detection is refreshed on each call so old tasks adapt when a
    project moves between git and non-git contexts.
    """
    meta = ensure_task_meta(task)
    workflow = meta.get("workflow")
    if not isinstance(workflow, dict):
        workflow = {}
        meta["workflow"] = workflow

    defaults = default_workflow_state(
        repo_root,
        current_step=current_step or STEP_AWAITING_IMPLEMENT,
    )

    if not isinstance(workflow.get("version"), int):
        workflow["version"] = defaults["version"]

    stored_step = workflow.get("current_step")
    if current_step is not None:
        workflow["current_step"] = current_step
    elif stored_step not in WORKFLOW_STEPS:
        workflow["current_step"] = defaults["current_step"]

    vcs = _ensure_dict(workflow, "vcs", defaults["vcs"])
    detected_vcs = detect_vcs(repo_root)
    vcs["kind"] = detected_vcs["kind"]
    vcs["commit_required"] = detected_vcs["commit_required"]

    _ensure_dict(workflow, "implement", defaults["implement"])
    _ensure_dict(workflow, "check", defaults["check"])
    _ensure_dict(workflow, "spec_update", defaults["spec_update"])
    _ensure_dict(workflow, "commit", defaults["commit"])

    return workflow


def ensure_workflow_for_start(task: dict, repo_root: Path) -> dict:
    """Initialize workflow state for a task that just entered implementation."""
    return ensure_workflow_state(task, repo_root, current_step=STEP_AWAITING_IMPLEMENT)


def mark_workflow_event(task_json_path: Path, repo_root: Path, event: str) -> dict:
    """Apply a workflow event to ``task_json_path`` and persist the result."""
    if event not in WORKFLOW_EVENTS:
        allowed = ", ".join(WORKFLOW_EVENTS)
        raise WorkflowError(f"Unknown workflow event '{event}'. Allowed events: {allowed}")

    original = _read_task_json(task_json_path)
    task = copy.deepcopy(original)
    workflow = ensure_workflow_state(task, repo_root)
    _apply_event(task, workflow, repo_root, event)

    if not write_json(task_json_path, task):
        raise WorkflowError(f"Failed to write task.json: {task_json_path}")
    return workflow


def guard_workflow_action(task_json_path: Path, repo_root: Path, action: str) -> GuardResult:
    """Check whether a workflow action is currently allowed.

    Guard calls lazy-initialize missing workflow state for legacy tasks. The
    initialization is persisted even when the guard itself blocks the action.
    """
    if action not in WORKFLOW_ACTIONS:
        allowed = ", ".join(WORKFLOW_ACTIONS)
        raise WorkflowError(f"Unknown workflow action '{action}'. Allowed actions: {allowed}")

    task = _read_task_json(task_json_path)
    workflow = ensure_workflow_state(task, repo_root)
    if not write_json(task_json_path, task):
        raise WorkflowError(f"Failed to write task.json: {task_json_path}")

    return _evaluate_guard(task, workflow, repo_root, action)


def build_check_snapshot(repo_root: Path) -> dict:
    """Capture the code-relevant freshness data for a completed check."""
    vcs = detect_vcs(repo_root)
    return {
        "fingerprint": compute_code_fingerprint(repo_root),
        "head": get_git_head(repo_root) if vcs["kind"] == VCS_GIT else None,
    }


def compute_code_fingerprint(repo_root: Path) -> str:
    """Return a content fingerprint for code-relevant project files."""
    vcs = detect_vcs(repo_root)
    if vcs["kind"] == VCS_GIT:
        return _git_code_fingerprint(repo_root)
    return _filesystem_code_fingerprint(repo_root)


def _ensure_dict(parent: dict, key: str, defaults: dict) -> dict:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    for default_key, default_value in defaults.items():
        if default_key not in value:
            value[default_key] = copy.deepcopy(default_value)
    return value


def _read_task_json(task_json_path: Path) -> dict:
    task = read_json(task_json_path)
    if not isinstance(task, dict):
        raise WorkflowError(f"Failed to read task.json: {task_json_path}")
    return task


def _apply_event(task: dict, workflow: dict, repo_root: Path, event: str) -> None:
    status = str(task.get("status") or "")
    if status != "in_progress":
        raise WorkflowError(
            f"Cannot apply workflow event '{event}' while task status is {status or 'unknown'}; expected in_progress."
        )

    current_step = str(workflow.get("current_step") or STEP_AWAITING_IMPLEMENT)
    now = utc_timestamp()

    if event == EVENT_IMPLEMENT_DISPATCHED:
        _require_step(current_step, STEP_AWAITING_IMPLEMENT, event)
        workflow["implement"]["dispatched_at"] = now
        return

    if event == EVENT_IMPLEMENT_COMPLETED:
        _require_step(current_step, STEP_AWAITING_IMPLEMENT, event)
        workflow["implement"]["completed_at"] = now
        workflow["current_step"] = STEP_AWAITING_CHECK
        return

    if event == EVENT_CHECK_COMPLETED:
        _apply_check_completed_event(workflow, repo_root, current_step, now, event)
        return

    if event in (EVENT_SPEC_REVIEWED_UPDATED, EVENT_SPEC_REVIEWED_NOOP):
        _require_step(current_step, STEP_AWAITING_SPEC_REVIEW, event)
        workflow["spec_update"]["reviewed_at"] = now
        workflow["spec_update"]["result"] = "updated" if event == EVENT_SPEC_REVIEWED_UPDATED else "noop"
        workflow["current_step"] = (
            STEP_AWAITING_COMMIT
            if _commit_required(workflow)
            else STEP_READY_TO_FINISH
        )
        return

    if event == EVENT_COMMIT_RECORDED:
        _require_step(current_step, STEP_AWAITING_COMMIT, event)
        if not _commit_required(workflow):
            raise WorkflowError("Commit recording is not required for non-git repositories.")
        freshness_error = _check_freshness_error(workflow, repo_root)
        if freshness_error:
            raise WorkflowError(freshness_error)
        head = get_git_head(repo_root)
        if not head:
            raise WorkflowError("Cannot record commit because git HEAD is unavailable.")
        workflow["commit"]["hash"] = head
        workflow["commit"]["recorded_at"] = now
        workflow["current_step"] = STEP_READY_TO_FINISH
        return

    if event == EVENT_READY_TO_FINISH:
        _require_step(current_step, STEP_READY_TO_FINISH, event)
        return

    raise WorkflowError(f"Unhandled workflow event: {event}")


def _evaluate_guard(task: dict, workflow: dict, repo_root: Path, action: str) -> GuardResult:
    current_step = str(workflow.get("current_step") or STEP_AWAITING_IMPLEMENT)
    status = str(task.get("status") or "")

    if action == ACTION_START:
        if status == "completed":
            return _blocked(current_step, "Completed tasks cannot be started.")
        if status == "planning" and not can_enter_implementation(task):
            prd_status = get_prd_status(task)
            return _blocked(
                current_step,
                f"Cannot start while PRD is unconfirmed (prd_status={prd_status}).",
            )
        return _allowed(current_step, "Workflow start guard passed.")

    if action == ACTION_DISPATCH_IMPLEMENT:
        return _require_guard_step(
            status,
            current_step,
            STEP_AWAITING_IMPLEMENT,
            "Implementation dispatch is only allowed after task.py start.",
        )

    if action == ACTION_DISPATCH_CHECK:
        return _require_guard_step(
            status,
            current_step,
            STEP_AWAITING_CHECK,
            "Check dispatch is only allowed after implementation is completed.",
        )

    if action == ACTION_REVIEW_SPEC:
        return _require_guard_step(
            status,
            current_step,
            STEP_AWAITING_SPEC_REVIEW,
            "Spec review is only allowed after check completion.",
        )

    if action == ACTION_COMMIT:
        if not _commit_required(workflow):
            return _allowed(current_step, "Commit is not required for non-git repositories.")
        if current_step != STEP_AWAITING_COMMIT:
            return _blocked(
                current_step,
                f"Commit is blocked until current_step={STEP_AWAITING_COMMIT}.",
            )
        freshness_error = _check_freshness_error(workflow, repo_root)
        if freshness_error:
            return _blocked(current_step, freshness_error)
        return _allowed(current_step, "Workflow commit guard passed.")

    if action in (ACTION_FINISH, ACTION_ARCHIVE):
        if current_step != STEP_READY_TO_FINISH:
            return _blocked(
                current_step,
                f"{action} is blocked until current_step={STEP_READY_TO_FINISH}.",
            )
        freshness_error = _check_freshness_error(workflow, repo_root)
        if freshness_error:
            return _blocked(current_step, freshness_error)
        if _commit_required(workflow):
            commit_error = _commit_recording_error(workflow, repo_root)
            if commit_error:
                return _blocked(current_step, commit_error)
        return _allowed(current_step, f"Workflow {action} guard passed.")

    return _blocked(current_step, f"Unhandled workflow action: {action}")


def _require_guard_step(
    status: str,
    current_step: str,
    expected_step: str,
    message: str,
) -> GuardResult:
    if status != "in_progress":
        return _blocked(current_step, "Task must be in_progress for this workflow action.")
    if current_step != expected_step:
        return _blocked(current_step, message)
    return _allowed(current_step, "Workflow guard passed.")


def _require_step(current_step: str, expected_step: str, event: str) -> None:
    if current_step != expected_step:
        raise WorkflowError(
            f"Cannot apply event '{event}' from current_step={current_step}; expected {expected_step}."
        )


def _apply_check_completed_event(
    workflow: dict,
    repo_root: Path,
    current_step: str,
    now: str,
    event: str,
) -> None:
    if current_step not in _CHECK_COMPLETED_STEPS:
        expected_steps = ", ".join(_CHECK_COMPLETED_STEPS[:-1])
        raise WorkflowError(
            f"Cannot apply event '{event}' from current_step={current_step}; "
            f"expected {expected_steps}, or {_CHECK_COMPLETED_STEPS[-1]}."
        )

    snapshot = build_check_snapshot(repo_root)
    workflow["check"]["completed_at"] = now
    workflow["check"]["fingerprint"] = snapshot["fingerprint"]
    workflow["check"]["head"] = snapshot["head"]

    if current_step in (STEP_AWAITING_COMMIT, STEP_READY_TO_FINISH):
        if _commit_required(workflow):
            workflow["commit"]["hash"] = None
            workflow["commit"]["recorded_at"] = None
            workflow["current_step"] = STEP_AWAITING_COMMIT
        else:
            workflow["current_step"] = STEP_READY_TO_FINISH
        return

    workflow["current_step"] = STEP_AWAITING_SPEC_REVIEW


def _check_freshness_error(workflow: dict, repo_root: Path) -> str | None:
    check = workflow.get("check")
    if not isinstance(check, dict):
        return "Workflow check has not been completed."
    expected = check.get("fingerprint")
    if not check.get("completed_at") or not isinstance(expected, str) or not expected:
        return "Workflow check has not been completed."
    current = compute_code_fingerprint(repo_root)
    if current != expected:
        return "Code-relevant changes occurred after check-completed; run trellis-check and mark check-completed again."
    return None


def _commit_recording_error(workflow: dict, repo_root: Path) -> str | None:
    commit = workflow.get("commit")
    if not isinstance(commit, dict):
        return "A recorded git commit is required before finish/archive."
    recorded_hash = commit.get("hash")
    if not isinstance(recorded_hash, str) or not recorded_hash:
        return "A recorded git commit is required before finish/archive."
    head = get_git_head(repo_root)
    if not head:
        return "Cannot verify recorded git commit because git HEAD is unavailable."
    if recorded_hash != head:
        return "Recorded git commit is stale; run commit-recorded again."
    return None


def _commit_required(workflow: dict) -> bool:
    vcs = workflow.get("vcs")
    if not isinstance(vcs, dict):
        return False
    return bool(vcs.get("commit_required"))


def _allowed(current_step: str, message: str) -> GuardResult:
    return GuardResult(True, message, current_step)


def _blocked(current_step: str, message: str) -> GuardResult:
    return GuardResult(False, message, current_step)


def _git_code_fingerprint(repo_root: Path) -> str:
    args = [
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        ".",
        *_GIT_EXCLUDED_PATHSPECS,
    ]
    rc, out, _ = run_git(args, cwd=repo_root)
    if rc != 0:
        return _filesystem_code_fingerprint(repo_root)
    paths = [path for path in out.split("\0") if path]
    return _hash_existing_files(repo_root, paths)


def _filesystem_code_fingerprint(repo_root: Path) -> str:
    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        current_dir = Path(dirpath)
        rel_dir = _relative_path(repo_root, current_dir)
        kept_dirnames = []
        for dirname in dirnames:
            rel_path = dirname if rel_dir == "." else f"{rel_dir}/{dirname}"
            if not _is_non_code_path(rel_path) and _normalize_rel_path(rel_path) != ".git":
                kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames
        for filename in filenames:
            rel_path = filename if rel_dir == "." else f"{rel_dir}/{filename}"
            if not _is_non_code_path(rel_path):
                paths.append(rel_path)
    return _hash_existing_files(repo_root, paths)


def _hash_existing_files(repo_root: Path, paths: list[str]) -> str:
    digest = hashlib.sha256()
    for rel_path in sorted({_normalize_rel_path(path) for path in paths}):
        if not rel_path or _is_non_code_path(rel_path):
            continue
        file_path = repo_root / Path(rel_path)
        if not file_path.is_file():
            continue
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_digest(file_path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _file_digest(file_path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        digest.update(b"<unreadable>")
    return digest.hexdigest()


def _relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix() or "."
    except ValueError:
        return path.as_posix()


def _normalize_rel_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _is_non_code_path(path: str) -> bool:
    normalized = _normalize_rel_path(path)
    if normalized == ".git" or normalized.startswith(".git/"):
        return True
    for prefix in _NON_CODE_PREFIXES:
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return True
    return False
