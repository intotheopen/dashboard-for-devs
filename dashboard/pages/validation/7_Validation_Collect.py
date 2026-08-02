"""Validation Pipeline — Collect and predict (Lane A–first corpus console).

Phase 11: Lane A same-age grades instantly (no wait). Lane B 24/48/72h waits
are inactive unless VALIDATION_FIXED_HORIZON_ENABLED=true.
"""

import asyncio
import importlib
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

import config.settings as _settings_mod  # noqa: E402

# Streamlit often keeps a pre-Phase-11 Settings class after hot-reload.
if not hasattr(_settings_mod.Settings, "validation_multi_horizon_enabled"):
    _settings_mod = importlib.reload(_settings_mod)

load_settings = _settings_mod.load_settings
from dashboard.chrome import (  # noqa: E402
    page_header,
    pipeline_flow_strip,
    render_phase_badges,
    section_header,
)
from dashboard.validation_collect_ui import (  # noqa: E402
    render_advanced_one_off,
    render_dataset_inventory,
    render_destination_card,
    render_import_result_banner,
    render_lane_mode_banner,
    render_one_off_result,
    render_predict_actions,
    render_progress_strip,
    render_time_stats,
    store_run_timing,
)
from telemetry.apify import load_apify_runs  # noqa: E402
from telemetry.apify_ui import render_apify_cost_history, render_apify_session_cost  # noqa: E402
from validation_pipeline.collect_dashboard import (  # noqa: E402
    build_collect_dashboard_snapshot,
)
from validation_pipeline.corpus_import import (  # noqa: E402
    collected_posts_from_saved_collection,
)
from validation_pipeline.pipeline import (  # noqa: E402
    run_collect_and_predict,
    run_predict_on_posts,
)
import validation_pipeline.reset as _reset_mod  # noqa: E402

# Force-reload so Streamlit does not keep a pre-feedback_jobs wipe.
_reset_mod = importlib.reload(_reset_mod)
reset_validation_data_for_settings = _reset_mod.reset_validation_data_for_settings
from validation_pipeline.vectorized_corpus import (  # noqa: E402
    bulk_import_vectorized_and_predict,
)

st.set_page_config(page_title="Collect and predict", layout="wide")
page_header(
    "Collect and predict",
    "Predict vectorized datasets automatically with **Lane A** — same-age grades, "
    "no wait. See how much is left, where results go, and time estimates in one place.",
    step_hint=(
        "Validation step 1 of 4 · Next: Validation queue · "
        "After grading: Accuracy over time · Phase 11"
    ),
)
pipeline_flow_strip("validation", "predict")
render_phase_badges(["0"])

settings = load_settings()
snapshot = build_collect_dashboard_snapshot(settings)
has_datasets = bool(snapshot.datasets)

section_header(
    "Predict vectorized corpus (Lane A)",
    """
Uses analysed LinkedIn **CSV/JSONL bundles with matching `.npy` embeddings**
from **Make embeddings**. Posts are deduped by `post_id`, then predicted.

**Lane A** (`same_age`) grades immediately against pre-strip engagement — no Apify
rescrape. **Lane B** (24/48/72h) waits for rescrape and stays inactive when
`VALIDATION_FIXED_HORIZON_ENABLED=false`.

Per-run Gemini cap: `VALIDATION_MULTI_HORIZON_MAX_PREDICTS_PER_RUN`.
""",
)

render_lane_mode_banner(snapshot, settings)

# Max posts widget is inside actions; use session default for ETA strip first pass.
_preview_max = int(
    st.session_state.get(
        "vectorized_import_max",
        min(50, snapshot.corpus_unique or snapshot.vector_sum or 1),
    )
)
render_progress_strip(snapshot, max_posts=_preview_max)
render_destination_card(snapshot)

section_header(
    "Time & statistics",
    "ETA uses your last run pace when available (otherwise ~4s/post including pause). "
    "Age buckets show how already-predicted Lane A rows are distributed.",
)
render_time_stats(snapshot, max_posts=_preview_max)

section_header(
    "Dataset inventory",
    "Each row is an analysed JSONL paired with its embedding matrix. "
    "Unique ids come from `.npy.meta.json` when present.",
)
render_dataset_inventory(snapshot)

section_header(
    "Run predictions",
    "Primary action predicts the next batch of posts missing Lane A. "
    "Reset clears validation/feedback rows only — corpus posts stay.",
)
bulk_max, reset_clicked, redo_clicked, predict_clicked = render_predict_actions(
    snapshot,
    settings,
    has_datasets=has_datasets,
)

if reset_clicked:
    reset = reset_validation_data_for_settings(settings)
    st.session_state["validation_reset_counts"] = reset
    st.session_state.pop("vectorized_import_result", None)
    st.rerun()

if redo_clicked:
    st.session_state["validation_redo_requested"] = True

render_import_result_banner()


def _run_bulk_predict(*, max_posts: int, progress_label: str) -> None:
    started = time.perf_counter()
    progress = st.progress(0, text=progress_label)

    def on_progress(completed: int, total: int, message: str) -> None:
        fraction = (completed / total) if total else 1.0
        label = f"{completed}/{total} — {message}" if total else message
        progress.progress(min(max(fraction, 0.0), 1.0), text=label)

    result = bulk_import_vectorized_and_predict(
        settings,
        max_posts=int(max_posts),
        on_progress=on_progress,
    )
    elapsed = time.perf_counter() - started
    store_run_timing(
        seconds=elapsed,
        imported=getattr(result, "imported", 0),
        skipped=getattr(result, "skipped", 0),
        errors=len(getattr(result, "errors", []) or []),
    )
    progress.progress(
        1.0,
        text=(
            f"Done — imported={result.imported} skipped={result.skipped} "
            f"errors={len(result.errors)}"
        ),
    )
    st.session_state["vectorized_import_result"] = result
    st.rerun()


if st.session_state.pop("validation_redo_requested", False):
    reset = reset_validation_data_for_settings(settings)
    st.session_state["validation_reset_counts"] = reset
    _run_bulk_predict(
        max_posts=bulk_max,
        progress_label="Reset done — re-predicting vectorized corpus...",
    )

if predict_clicked:
    _run_bulk_predict(
        max_posts=bulk_max,
        progress_label="Lane A predict on vectorized corpus...",
    )

st.divider()

advanced = render_advanced_one_off(settings)
if advanced:
    log = st.empty()
    messages: list[str] = []

    def on_one_off_progress(msg: str) -> None:
        messages.append(msg)
        log.code("\n".join(messages[-8:]))

    started = time.perf_counter()
    with st.spinner("Running collect/predict..."):
        if advanced["source_mode"] == "Live Apify scrape":
            search_params = {
                "searchQueries": [advanced["search_query"].strip()],
                "maxPosts": int(advanced["max_posts"]),
                "sortBy": "relevance",
            }
            result = asyncio.run(
                run_collect_and_predict(
                    search_params,
                    settings=settings,
                    on_progress=on_one_off_progress,
                )
            )
            st.session_state["last_apify_runs"] = load_apify_runs(settings, limit=20)
        else:
            from config.paths import resolve_data_path

            path = resolve_data_path(settings.raw_data_dir) / advanced["selected_scan"]
            posts = collected_posts_from_saved_collection(
                path, settings, max_posts=int(advanced["max_posts"])
            )
            result = asyncio.run(
                run_predict_on_posts(
                    posts,
                    settings=settings,
                    on_progress=on_one_off_progress,
                )
            )
    store_run_timing(
        seconds=time.perf_counter() - started,
        imported=getattr(result, "predicted", 0),
        skipped=getattr(result, "skipped", 0),
        errors=len(getattr(result, "errors", []) or []),
        predicted=getattr(result, "predicted", 0),
    )
    st.session_state["validation_last_result"] = result
    st.rerun()

if "validation_last_result" in st.session_state:
    render_one_off_result(st.session_state["validation_last_result"])

st.divider()
_session_runs = st.session_state.get("last_apify_runs") or []
if _session_runs:
    render_apify_session_cost(_session_runs)
render_apify_cost_history(settings)
