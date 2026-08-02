"""Collect and predict — Lane A–first Streamlit panels."""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from validation_pipeline.collect_dashboard import CollectDashboardSnapshot

_DEFAULT_SEC_PER_POST = 4.0


def _format_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60.0
    if minutes < 60:
        return f"{minutes:.1f} min"
    hours = minutes / 60.0
    return f"{hours:.1f} h"


def _seconds_per_post_from_session() -> float:
    timing = st.session_state.get("collect_last_run_timing") or {}
    duration = timing.get("seconds")
    predicted = timing.get("predicted") or timing.get("imported")
    if duration and predicted and float(predicted) > 0:
        return max(0.5, float(duration) / float(predicted))
    return _DEFAULT_SEC_PER_POST


def render_lane_mode_banner(
    snapshot: CollectDashboardSnapshot,
    settings: Any,
) -> None:
    """Lane A active / Lane B inactive (or secondary waiting)."""
    if snapshot.lane_a_only:
        st.success(
            "**Lane A active** — same-age grades with **no wait** (instant validate). "
            "**Lane B inactive** — 24/48/72h predicts + Apify rescrapes are off "
            "(`VALIDATION_FIXED_HORIZON_ENABLED=false`)."
        )
    else:
        horizons = list(
            getattr(settings, "validation_fixed_horizons_hours", (24, 48, 72)) or (24, 48, 72)
        )
        waiting = snapshot.lane_b_scheduled
        st.info(
            f"**Lane A** grades immediately (no wait). **Lane B** schedules "
            f"{horizons}h rows"
            + (f" — **{waiting}** waiting for rescrape." if waiting else ".")
        )
    st.caption(f"Predictor model: `{snapshot.model_name}`")


def render_progress_strip(
    snapshot: CollectDashboardSnapshot,
    *,
    max_posts: int,
) -> None:
    """Corpus / predicted / remaining / run budget."""
    cols = st.columns(4)
    cols[0].metric(
        "Corpus unique",
        snapshot.corpus_unique,
        help="Deduped post ids from embedding meta (falls back to vector counts).",
    )
    cols[1].metric(
        "Predicted (Lane A)",
        snapshot.predicted_lane_a,
        help="Distinct posts with a same-age prediction row.",
    )
    cols[2].metric(
        "Left to predict",
        snapshot.remaining_lane_a,
        help="max(0, corpus unique − Lane A predicted).",
    )
    budget = min(int(max_posts), int(snapshot.max_predicts_per_run))
    cols[3].metric(
        "This run budget",
        budget,
        help=f"Min of Max posts and per-run cap ({snapshot.max_predicts_per_run}).",
    )

    total = snapshot.corpus_unique
    done = snapshot.predicted_lane_a
    if total > 0:
        fraction = min(1.0, done / total)
        st.progress(
            fraction,
            text=f"Lane A coverage: {done:,} / {total:,} ({100 * fraction:.0f}%)",
        )
    elif not snapshot.datasets:
        st.warning(
            "No vectorized LinkedIn datasets found. Complete **Analyse posts** then "
            "**Make embeddings** under Build the corpus first."
        )
    if not snapshot.database_available:
        st.caption("Database stats unavailable — remaining uses corpus file counts only.")


def render_destination_card(snapshot: CollectDashboardSnapshot) -> None:
    """Where predictions go next (prose; no page_link)."""
    st.markdown(
        """
**Where predictions go**

1. **Lane A** → Gemini predict → **instant grade** (no Apify) → **Validation queue**
   as `validated` → **Accuracy over time** / **Feedback loop**
2. **Lane B** → schedule until `posted_at + H` → Apify rescrape → grade
"""
    )
    if snapshot.lane_a_only:
        st.caption("Lane B path is inactive with current settings.")
    else:
        st.caption(
            f"Lane B waiting (scheduled fixed-horizon rows): **{snapshot.lane_b_scheduled}**."
        )


def render_time_stats(
    snapshot: CollectDashboardSnapshot,
    *,
    max_posts: int,
) -> None:
    """Grouped ETA and age-bucket statistics."""
    sec = _seconds_per_post_from_session()
    run_n = min(int(max_posts), int(snapshot.max_predicts_per_run), max(snapshot.remaining_lane_a, 0) or int(max_posts))
    this_run_eta = run_n * sec
    remaining_eta = snapshot.remaining_lane_a * sec

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Est. sec / post", f"{sec:.1f}")
    c2.metric("ETA this run", _format_duration(this_run_eta))
    c3.metric("ETA remaining corpus", _format_duration(remaining_eta))
    c4.metric("Predicted last 24h", snapshot.predicted_last_24h)

    timing = st.session_state.get("collect_last_run_timing")
    if timing:
        st.caption(
            f"Last run: {_format_duration(float(timing.get('seconds') or 0))} · "
            f"imported={timing.get('imported', '—')} skipped={timing.get('skipped', '—')} "
            f"errors={timing.get('errors', '—')}"
        )
    else:
        st.caption(
            "Default pace ~4s/post (Gemini + 1s pause). Updates after your next predict run."
        )

    if snapshot.age_bucket_counts:
        rows = sorted(
            snapshot.age_bucket_counts.items(),
            key=lambda item: item[0],
        )
        st.markdown("**Lane A age buckets** (already predicted)")
        st.dataframe(
            [{"age_bucket": k, "predictions": v} for k, v in rows],
            hide_index=True,
            use_container_width=True,
        )


def render_dataset_inventory(snapshot: CollectDashboardSnapshot) -> None:
    """Table of vectorized datasets ready for predict."""
    if not snapshot.datasets:
        return
    st.dataframe(
        [
            {
                "dataset": row.jsonl_name,
                "embeddings": row.embeddings_name,
                "vectors": row.vector_count,
                "unique_ids": row.unique_ids_available,
                "meta_ids": "yes" if row.has_meta_ids else "fallback",
                "bundle": row.bundle_id or "—",
            }
            for row in snapshot.datasets
        ],
        hide_index=True,
        use_container_width=True,
    )


def render_predict_actions(
    snapshot: CollectDashboardSnapshot,
    settings: Any,
    *,
    has_datasets: bool,
) -> tuple[int, bool, bool, bool]:
    """Reset / redo / max posts / primary predict.

    Returns ``(bulk_max, reset_clicked, redo_clicked, predict_clicked)``.
    """
    default_max = min(50, snapshot.corpus_unique or snapshot.vector_sum or 1)
    if "vectorized_import_max" not in st.session_state:
        st.session_state["vectorized_import_max"] = default_max
    col_reset, col_redo, col_max = st.columns(3)
    with col_reset:
        reset_clicked = st.button(
            "Reset validation data",
            help="Clear predictions, snapshots, feedback rows, and cluster stats. "
            "Does not delete corpus posts.",
        )
    with col_redo:
        can_redo = bool(
            settings.database_url and settings.gemini_api_key and has_datasets
        )
        redo_clicked = st.button(
            "Reset and redo predictions",
            type="secondary",
            disabled=not can_redo,
            help="Wipe validation/feedback rows (posts stay), then re-predict the "
            "vectorized corpus (Lane A focus).",
        )
    with col_max:
        bulk_max = st.number_input(
            "Max posts",
            min_value=1,
            max_value=2000,
            key="vectorized_import_max",
            help="How many posts to predict this run. Scans newest datasets until full.",
        )

    can_bulk = bool(settings.database_url and settings.gemini_api_key and has_datasets)
    if snapshot.lane_a_only:
        st.caption(
            "Predicts **Lane A only** (same-age instant grades) with "
            f"**{getattr(settings, 'validation_predict_workers', 10)} parallel** "
            f"Gemini workers under the per-run budget "
            f"(cap {snapshot.max_predicts_per_run})."
        )
    else:
        st.caption(
            "Runs Lane A plus Lane B fixed horizons with "
            f"**{getattr(settings, 'validation_predict_workers', 10)} parallel** "
            f"Gemini workers (cap {snapshot.max_predicts_per_run})."
        )

    predict_clicked = st.button(
        "Predict next N (Lane A)",
        type="primary",
        disabled=not can_bulk,
    )
    return int(bulk_max), reset_clicked, redo_clicked, predict_clicked


def render_import_result_banner() -> None:
    """Show last bulk import / reset banners from session state."""
    if "validation_reset_counts" in st.session_state:
        reset = st.session_state["validation_reset_counts"]
        st.success(
            f"Reset complete — predictions={reset.predictions}, "
            f"feedback={reset.prediction_feedback}, clusters={reset.prediction_clusters}"
        )

    if "vectorized_import_result" in st.session_state:
        bulk = st.session_state["vectorized_import_result"]
        imported = getattr(bulk, "imported", 0)
        st.success(
            f"Vectorized import: loaded={getattr(bulk, 'loaded', 0)} "
            f"imported={imported} skipped={getattr(bulk, 'skipped', 0)} "
            f"errors={len(getattr(bulk, 'errors', []) or [])}. "
            f"**{imported}** graded immediately — open **Validation queue** "
            "(Validated) or **Accuracy over time**."
        )
        for err in (getattr(bulk, "errors", None) or [])[:10]:
            st.error(err)


def render_advanced_one_off(
    settings: Any,
) -> dict[str, Any]:
    """Advanced expander controls for live scrape / saved collection.

    Returns a dict of run parameters when the user clicks run; otherwise empty.
    """
    with st.expander("Advanced: one-off scrape or saved collection", expanded=False):
        source_mode = st.radio(
            "Source",
            ["Live Apify scrape", "Saved collection (Collect samples)"],
            help="Saved collections are the linkedin_*.json files from Collect samples.",
            key="collect_advanced_source",
        )
        max_posts = st.number_input(
            "Max posts (one-off)",
            min_value=1,
            max_value=100,
            value=settings.validation_max_posts_per_run,
            key="collect_advanced_max_posts",
        )

        if settings.validation_multi_horizon_enabled:
            if getattr(settings, "validation_fixed_horizon_enabled", True):
                st.info(
                    "Multi-horizon: same-age grade now + 24/48/72h rescrape rows "
                    f"(budget ≤ {settings.validation_multi_horizon_max_predicts_per_run}/run)."
                )
            else:
                st.info(
                    "Lane A only: same-age instant grades. Lane B 24/48/72h predicts "
                    "+ rescrapes are OFF."
                )
        elif settings.validation_dev_window_minutes is not None:
            st.info(f"Dev validation window: {settings.validation_dev_window_minutes} minutes")
        else:
            st.info(f"Legacy window: {settings.validation_window_hours}h after publish")

        can_predict = bool(settings.gemini_api_key and settings.database_url)
        search_query = "ai marketing"
        selected_scan = "-- Select a saved collection --"
        run_clicked = False

        if source_mode == "Live Apify scrape":
            search_query = st.text_input(
                "Search query",
                value="ai marketing",
                key="collect_advanced_query",
            )
            can_run = can_predict and bool(
                settings.apify_api_token
                and settings.apify_actor_id
                and settings.apify_profile_actor_id
            )
            if not can_run:
                missing = []
                if not settings.apify_api_token:
                    missing.append("APIFY_API_TOKEN")
                if not settings.apify_actor_id:
                    missing.append("APIFY_ACTOR_ID")
                if not settings.apify_profile_actor_id:
                    missing.append("APIFY_PROFILE_ACTOR_ID")
                if not settings.gemini_api_key:
                    missing.append("GEMINI_API_KEY")
                if not settings.database_url:
                    missing.append("DATABASE_URL")
                st.warning(f"Missing: {', '.join(missing)}")
            run_clicked = st.button(
                "Run Collect + Predict",
                type="primary",
                disabled=not can_run,
                key="collect_advanced_run_live",
            )
        else:
            from validation_pipeline.corpus_import import list_saved_collections

            saved_scans = list_saved_collections(settings)
            if saved_scans:
                scan_options = ["-- Select a saved collection --"] + [
                    f.name for f in saved_scans
                ]
                selected_scan = st.selectbox(
                    "Saved collections",
                    scan_options,
                    help="Same files as Collect samples → Load Previous Collection.",
                    key="collect_advanced_scan",
                )
            else:
                from config.paths import resolve_data_path

                st.info(
                    f"No saved collections in `{resolve_data_path(settings.raw_data_dir)}`."
                )
            can_run = can_predict and selected_scan != "-- Select a saved collection --"
            run_clicked = st.button(
                "Run Predict on Collection",
                type="primary",
                disabled=not can_run,
                key="collect_advanced_run_saved",
            )

        if run_clicked:
            return {
                "source_mode": source_mode,
                "max_posts": int(max_posts),
                "search_query": search_query,
                "selected_scan": selected_scan,
            }
    return {}


def render_one_off_result(last: Any) -> None:
    """Success banner + predictions table for advanced one-off runs."""
    from validation_pipeline.ui import render_predictions_table

    st.success(
        f"scraped/loaded={last.scraped} predicted={last.predicted} "
        f"skipped={last.skipped} budget_skipped={getattr(last, 'budget_skipped', 0)} "
        f"errors={len(last.errors)}"
    )
    if last.errors:
        for err in last.errors[:10]:
            st.error(err)
    if last.predictions:
        render_predictions_table(last.predictions)


def store_run_timing(
    *,
    seconds: float,
    imported: int = 0,
    skipped: int = 0,
    errors: int = 0,
    predicted: Optional[int] = None,
) -> None:
    """Persist last-run timing for ETA estimates."""
    st.session_state["collect_last_run_timing"] = {
        "seconds": float(seconds),
        "imported": int(imported),
        "skipped": int(skipped),
        "errors": int(errors),
        "predicted": int(predicted if predicted is not None else imported),
    }
