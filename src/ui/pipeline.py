import base64
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.agents.answer_agent import draft_answer
from src.db import (
    add_question,
    approve_answer,
    delete_job,
    get_job,
    insert_job,
    job_exists,
    list_jobs,
    list_questions,
    update_job_fields,
    update_job_status,
)
from src.services import ACTIVE_STAGES, ALL_STATUSES, tailor_for_job
from src.ui.common import (
    NEXT_ACTIONS,
    STATUS_LABELS,
    parse_ts,
    rerun,
    require_api_key,
    story_todo_count,
)

SHORT_DESCRIPTION_CHARS = 700


def _delete_and_close(job_id):
    """Button callback: widget state may only be changed from a callback or before the widget exists."""
    delete_job(job_id)
    st.session_state["selected_job"] = None


def _set_status(job_id, status):
    update_job_status(job_id, status)
    rerun()


def _job_option_label(jobs_by_id):
    def fmt(job_id):
        if job_id is None:
            return "Choose a job to open"
        j = jobs_by_id.get(job_id)
        if not j:
            return "Job {}".format(job_id)
        fit = "" if j.get("fit_score") is None else "  (fit {})".format(int(j["fit_score"]))
        return "{}, {}{}".format(j["company"], j["title"], fit)

    return fmt


def _add_job_form():
    with st.expander("Add a job you found yourself"):
        st.caption(
            "Paste a posting from a company site or LinkedIn. It goes straight to To apply. "
            "Jobs you add yourself do not get a fit score."
        )
        with st.form("add_job_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            company = c1.text_input("Company")
            title = c2.text_input("Job title")
            c3, c4 = st.columns(2)
            location = c3.text_input("Location")
            url = c4.text_input("Link to the posting")
            description = st.text_area("Posting text", height=180, help="The full job description. Resume tailoring reads this.")
            submitted = st.form_submit_button("Add to pipeline", type="primary")
        if submitted:
            if not company.strip() or not title.strip():
                st.error("Add at least a company and a job title.")
            elif job_exists(company.strip(), title.strip(), url.strip() or None):
                st.warning("That job is already in your pipeline.")
            else:
                new_id = insert_job(
                    {
                        "company": company.strip(),
                        "title": title.strip(),
                        "location": location.strip() or None,
                        "apply_url": url.strip() or None,
                        "posting_source": "Added manually",
                        "description": description.strip() or None,
                    },
                    status="approved",
                )
                st.session_state["selected_job"] = new_id
                st.success("Added {}, {}. It is open below.".format(company.strip(), title.strip()))


def _table(jobs):
    rows = []
    for j in jobs:
        added = parse_ts(j.get("discovered_at"))
        rows.append(
            {
                "Company": j["company"],
                "Title": j["title"],
                "Fit": j.get("fit_score"),
                "Status": STATUS_LABELS.get(j["status"], j["status"]),
                "Location": j.get("location") or "",
                "Posting": j.get("apply_url"),
                "Added": added.strftime("%b %d") if added else "",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%d"),
            "Posting": st.column_config.LinkColumn("Posting", display_text="Open"),
        },
    )


def _pdf_preview(path):
    data = Path(path).read_bytes()
    st.download_button(
        "Download PDF",
        data=data,
        file_name=Path(path).name,
        mime="application/pdf",
        key="dl_{}".format(Path(path).name),
    )
    b64 = base64.b64encode(data).decode()
    st.markdown(
        '<iframe src="data:application/pdf;base64,{}" width="100%" height="860" '
        'style="border:1px solid #DDE2E8;border-radius:8px;background:#fff"></iframe>'.format(b64),
        unsafe_allow_html=True,
    )
    st.caption("If the preview is blank in your browser, use Download PDF instead.")


def _overview_tab(job):
    jid = job["id"]
    if job.get("fit_reasoning"):
        st.markdown("**Why it scored {}:** {}".format(
            "n/a" if job.get("fit_score") is None else int(job["fit_score"]), job["fit_reasoning"]
        ))
    if job.get("posting_source"):
        st.caption("Found via: {}".format(job["posting_source"]))

    st.markdown("**Posting text**")
    desc = st.text_area(
        "Posting text",
        value=job.get("description") or "",
        height=280,
        key="desc_{}".format(jid),
        label_visibility="collapsed",
    )
    if len(desc.strip()) < SHORT_DESCRIPTION_CHARS:
        st.info(
            "This is short. The search agent only saves a brief summary, so paste the full "
            "posting here before you tailor your resume. Tailoring can only emphasize what the "
            "text mentions."
        )
    if st.button("Save posting text", key="save_desc_{}".format(jid)):
        update_job_fields(jid, description=desc.strip() or None)
        st.success("Saved.")

    st.markdown("**Notes**")
    notes = st.text_area(
        "Notes",
        value=job.get("notes") or "",
        height=110,
        key="notes_{}".format(jid),
        label_visibility="collapsed",
        placeholder="Recruiter name, referral, interview dates, anything you want to remember.",
    )
    if st.button("Save notes", key="save_notes_{}".format(jid)):
        update_job_fields(jid, notes=notes.strip() or None)
        st.success("Saved.")

    with st.expander("Edit company, title, location or link"):
        c1, c2 = st.columns(2)
        company = c1.text_input("Company", value=job["company"], key="e_co_{}".format(jid))
        title = c2.text_input("Job title", value=job["title"], key="e_ti_{}".format(jid))
        c3, c4 = st.columns(2)
        location = c3.text_input("Location", value=job.get("location") or "", key="e_lo_{}".format(jid))
        url = c4.text_input("Link to the posting", value=job.get("apply_url") or "", key="e_ur_{}".format(jid))
        if st.button("Save details", key="save_details_{}".format(jid)):
            if not company.strip() or not title.strip():
                st.error("Company and job title cannot be empty.")
            else:
                update_job_fields(
                    jid,
                    company=company.strip(),
                    title=title.strip(),
                    location=location.strip() or None,
                    apply_url=url.strip() or None,
                )
                rerun()


def _resume_tab(job):
    jid = job["id"]
    if not (job.get("description") or "").strip():
        st.info("Paste the posting text on the Overview tab first. The tailoring step needs it.")
        return

    st.caption(
        "Tailoring only reorders your existing bullets and picks between wordings you have "
        "already approved. It never adds claims."
    )
    if st.button("Generate tailored resume", type="primary", key="tailor_{}".format(jid)):
        if require_api_key():
            with st.spinner("Tailoring your resume..."):
                try:
                    path, emphasis = tailor_for_job(jid)
                    st.session_state["emphasis_{}".format(jid)] = emphasis
                    job = get_job(jid)
                except Exception as e:  # surface API/network problems in the page
                    st.error("Could not tailor the resume: {}".format(e))

    path = job.get("tailored_resume_path")
    if path and Path(path).exists():
        emphasis = st.session_state.get("emphasis_{}".format(jid))
        if emphasis:
            st.markdown("**What it emphasized:** {}".format(emphasis))
        _pdf_preview(path)
        st.caption("Read it through before you attach it to a real application.")


def _questions_tab(job):
    jid = job["id"]
    todos = story_todo_count()
    if todos is None:
        st.warning("story_bank.seed.json is missing, so answers cannot be grounded in your stories yet.")
    elif todos:
        st.warning(
            "Your story bank still has {} TODO placeholder(s). Answers will read generic until "
            "you fill them in (data/story_bank.seed.json).".format(todos)
        )

    key = "newq_{}".format(jid)
    if st.session_state.pop("clear_{}".format(key), False):
        st.session_state[key] = ""
    prompt = st.text_area(
        "Application question",
        key=key,
        height=100,
        placeholder="Paste a short-answer question from the application, for example: Why are you interested in this role?",
    )
    if st.button("Draft answer", type="primary", key="draft_{}".format(jid)):
        if not prompt.strip():
            st.error("Paste a question first.")
        elif require_api_key():
            with st.spinner("Drafting from your story bank..."):
                try:
                    result = draft_answer(prompt.strip())
                    add_question(jid, prompt.strip(), result["draft"], result["story_slugs_used"])
                    st.session_state["clear_{}".format(key)] = True
                    rerun()
                except Exception as e:
                    st.error("Could not draft an answer: {}".format(e))

    questions = list_questions(jid)
    if not questions:
        st.markdown('<p class="muted">No questions yet. Drafts you save will be listed here.</p>', unsafe_allow_html=True)
    for q in reversed(questions):
        st.divider()
        st.markdown("**{}**".format(q["prompt"]))
        text = st.text_area(
            "Answer",
            value=q.get("approved_answer") or q.get("draft_answer") or "",
            height=190,
            key="ans_{}".format(q["id"]),
            label_visibility="collapsed",
        )
        slugs = []
        try:
            slugs = json.loads(q.get("story_slugs_used") or "[]")
        except ValueError:
            pass
        status = "Final answer saved" if q.get("approved_answer") else "Draft"
        st.caption("{}. Drawn from: {}".format(status, ", ".join(slugs) if slugs else "no stories"))
        if st.button("Save as final answer", key="approve_{}".format(q["id"])):
            approve_answer(q["id"], text.strip())
            st.success("Saved.")


def _job_detail(job):
    jid = job["id"]
    st.subheader("{}, {}".format(job["company"], job["title"]))
    meta = [STATUS_LABELS.get(job["status"], job["status"])]
    if job.get("location"):
        meta.append(job["location"])
    if job.get("fit_score") is not None:
        meta.append("fit {}".format(int(job["fit_score"])))
    st.caption(", ".join(meta))

    actions = NEXT_ACTIONS.get(job["status"], [])
    cols = st.columns(len(actions) + (1 if job.get("apply_url") else 0) or 1)
    for i, (label, target) in enumerate(actions):
        if cols[i].button(label, type="primary" if i == 0 else "secondary", key="act_{}_{}".format(jid, target)):
            _set_status(jid, target)
    if job.get("apply_url"):
        cols[len(actions)].link_button("Open posting", job["apply_url"])

    with st.expander("Change status or remove this job"):
        new_status = st.selectbox(
            "Status",
            ALL_STATUSES,
            index=ALL_STATUSES.index(job["status"]) if job["status"] in ALL_STATUSES else 0,
            format_func=lambda s: STATUS_LABELS.get(s, s),
            key="status_pick_{}".format(jid),
        )
        if st.button("Update status", key="status_save_{}".format(jid)):
            _set_status(jid, new_status)
        st.write("")
        confirm = st.checkbox("I want to delete this job and its saved answers", key="del_ok_{}".format(jid))
        st.button(
            "Delete job",
            disabled=not confirm,
            key="del_{}".format(jid),
            on_click=_delete_and_close,
            args=(jid,),
        )

    tab1, tab2, tab3 = st.tabs(["Overview", "Resume", "Application questions"])
    with tab1:
        _overview_tab(job)
    with tab2:
        _resume_tab(job)
    with tab3:
        _questions_tab(job)


def render():
    st.title("Pipeline")
    _add_job_form()

    jobs = list_jobs()
    if not jobs:
        st.markdown(
            '<p class="lede">No jobs yet. Run a search from the Search page, or add one above.</p>',
            unsafe_allow_html=True,
        )
        return

    f1, f2, f3 = st.columns([3, 2, 2])
    statuses = f1.multiselect(
        "Show",
        ALL_STATUSES,
        default=ACTIVE_STAGES,
        format_func=lambda s: STATUS_LABELS.get(s, s),
    )
    text = f2.text_input("Search", placeholder="Company, title or city")
    min_fit = f3.slider("Minimum fit", 0, 100, 0, step=5)

    needle = text.strip().lower()
    filtered = []
    for j in jobs:
        if j["status"] not in statuses:
            continue
        if needle and needle not in " ".join([j["company"], j["title"], j.get("location") or ""]).lower():
            continue
        score = j.get("fit_score")
        if min_fit and (score is None or score < min_fit):
            continue
        filtered.append(j)

    st.caption("Showing {} of {} jobs.".format(len(filtered), len(jobs)))
    if filtered:
        _table(filtered)
    else:
        st.markdown(
            '<p class="muted">Nothing matches these filters. Widen the status list or lower the minimum fit.</p>',
            unsafe_allow_html=True,
        )

    jobs_by_id = {j["id"]: j for j in jobs}
    options = [None] + [j["id"] for j in filtered]
    selected = st.session_state.get("selected_job")
    if selected is not None and selected not in jobs_by_id:
        selected = st.session_state["selected_job"] = None
    if selected is not None and selected not in options:
        options.append(selected)  # opened from elsewhere, keep it visible despite filters

    st.selectbox(
        "Open a job",
        options,
        format_func=_job_option_label(jobs_by_id),
        key="selected_job",
    )
    selected = st.session_state.get("selected_job")
    if selected is not None:
        st.divider()
        _job_detail(get_job(selected))
