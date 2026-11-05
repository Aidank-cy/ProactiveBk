"""Conservative trajectory features, cutoff candidates, and provisional labels."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

FEEDBACK_PATTERNS = {
    "missing_edge_case": r"\b(edge case|when (?:there is|there are|no |empty|missing)|empty|nil|null|zero|boundary|corner case)\b",
    "bug_report": r"\b(bug|fail(?:s|ed|ing)?|broken|crash|incorrect|doesn't work|does not work|regression)\b",
    "new_constraint": r"\b(must|should|need to|require[sd]?|cannot|can't|compatible|support)\b",
    "missing_implementation": r"\b(missing|forgot|also handle|please add|implement|not implemented)\b",
    "new_requirement": r"\b(please (?:add|include|support|ensure)|we need|it should|should also)\b",
    "code_quality": r"\b(refactor|rename|simplify|style|lint|readability|maintainab|documentation|test coverage)\b",
    "approval": r"\b(lgtm|looks good|approved|thanks|thank you)\b",
    "administrative": r"\b(merge|rebase|conflict|ci|workflow|release|changelog)\b",
    "clarification": r"\b(what do you mean|could you clarify|why|how does|is this intended)\b",
}
SUBSTANTIVE = {"missing_edge_case", "bug_report", "new_constraint", "missing_implementation", "new_requirement"}
COMMENT_TYPES = {"review", "review_comment", "issue_comment", "linked_issue_comment"}


def classify_feedback(text: str) -> tuple[str, bool]:
    """Exploratory high precision rules, never verified ground truth."""
    lower = (text or "").lower()
    if len(lower.strip()) < 12:
        return "other_uncertain", False
    hits = [name for name, pattern in FEEDBACK_PATTERNS.items() if re.search(pattern, lower)]
    if not hits:
        return "other_uncertain", False
    # Administrative and praise messages are not new requirements absent stronger evidence.
    for name in ("missing_edge_case", "bug_report", "missing_implementation", "new_requirement", "new_constraint"):
        if name in hits:
            return name, True
    return hits[0], False


def _dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _overlap(a: str, b: str) -> int:
    words = lambda x: {w for w in re.findall(r"[a-zA-Z]{4,}", x.lower())
                       if w not in {"this", "that", "with", "should", "please", "there", "have", "from"}}
    return len(words(a) & words(b))


def extract(data: dict, events: list[dict], cfg: dict):
    pr = data["pull"]
    author = (pr.get("user") or {}).get("login")
    comments = [e for e in events if e["event_type"] in COMMENT_TYPES]
    human = [e for e in comments if e["actor_type"] == "human"]
    reviewer = [e for e in human if e["event_type"] in {"review", "review_comment"}
                and e["actor"] != author]
    for event in comments:
        category, substantive = classify_feedback(event["content"])
        event["feedback_category"] = category
        event["substantive_candidate"] = bool(substantive and event["actor_type"] == "human"
                                               and event["actor"] != author)
        event["classification_status"] = "heuristic_unverified"
    feedback_candidates = [e for e in comments if e["substantive_candidate"]]
    commits = data["commits"]
    commit_shas = {c["sha"] for c in commits}
    # Timeline 'committed' can establish visibility. Commit author/committer dates cannot.
    visible_commits = [(e["timestamp"], e["commit_sha"]) for e in events
                       if e["event_type"] == "timeline_committed" and e["commit_sha"] in commit_shas]
    # A later requirement must follow observable implementation. A pre-code issue request is explicit context.
    reviews = [e for e in events if e["event_type"] == "review" and e["actor_type"] == "human"
               and e["actor"] != author]
    review_associations = [(e["timestamp"], e["commit_sha"]) for e in reviews if e["commit_sha"] in commit_shas]
    feedback = [e for e in feedback_candidates if
                e.get("commit_sha") in commit_shas or
                any(ts <= e["timestamp"] for ts, _ in visible_commits) or
                any(ts <= e["timestamp"] for ts, _ in review_associations)]
    review_rounds = len({e["timestamp"][:10] for e in reviews})
    # Count only observable timeline commit events after feedback; final commit list alone is insufficient.
    following = {}
    possible_following = {}
    commit_position = {c["sha"]: i for i, c in enumerate(commits)}
    for fb in feedback:
        later = [(ts, sha) for ts, sha in visible_commits if ts > fb["timestamp"]]
        following[fb["event_id"]] = sorted(later)[0][1] if later else None
        prior_sha = fb.get("commit_sha") if fb.get("commit_sha") in commit_shas else None
        if not prior_sha:
            earlier_associations = [(ts, sha) for ts, sha in review_associations
                                    if ts <= fb["timestamp"]]
            prior_sha = sorted(earlier_associations)[-1][1] if earlier_associations else None
        later_reviews = [(ts, sha) for ts, sha in review_associations
                         if ts > fb["timestamp"] and prior_sha and
                         commit_position[sha] > commit_position[prior_sha]]
        possible_following[fb["event_id"]] = sorted(later_reviews)[0][1] if later_reviews else None
    cutoffs = []
    for fb in feedback:
        sha = fb.get("commit_sha") if fb.get("commit_sha") in commit_shas else None
        prior_visible = [(ts, cs) for ts, cs in visible_commits if ts <= fb["timestamp"]]
        if not sha and prior_visible:
            sha = sorted(prior_visible)[-1][1]
        if not sha:
            prior_reviews = [(ts, cs) for ts, cs in review_associations if ts <= fb["timestamp"]]
            sha = sorted(prior_reviews)[-1][1] if prior_reviews else None
        if not sha:
            continue
        earlier = [e for e in events if e["timestamp"] < fb["timestamp"] and e["event_type"] != "pr_merged"]
        earlier_human = [e for e in earlier if e["actor_type"] == "human"]
        # Current title/body may have changed; only dated comments are safe as historical text.
        verified_context = " ".join(e["content"] for e in earlier_human
                                    if e["event_type"] in COMMENT_TYPES and e["evidence_status"] == "verified")
        overlap = _overlap(verified_context, fb["content"])
        earlier_ids = [e["event_id"] for e in earlier if e["evidence_status"] == "verified"
                       and not e.get("title_current_only") and not e.get("description_current_only")]
        state_confidence = ("review_associated_commit" if fb.get("commit_sha") == sha else
                            "timeline_commit" if prior_visible else "prior_review_associated_commit")
        grounded = True  # The actual later human message is evidence; semantic classification remains provisional.
        inferable = "possible" if _overlap(verified_context, fb["content"]) > 0 else "unknown"
        relevant = "possible" if overlap > 0 else "unknown"
        cutoff = {"repository": data["repository"], "pr_number": pr["number"],
                  "pr_url": pr["html_url"], "cutoff_timestamp": fb["timestamp"],
                  "cutoff_semantics": "immediately before feedback event; same-timestamp ordering uncertain",
                  "commit_sha": sha, "historical_event_ids": earlier_ids,
                  "explicit_requirement_candidates": [{"text": e["content"], "event_id": e["event_id"]}
                                                      for e in earlier_human if e["event_type"] in COMMENT_TYPES
                                                      and e["evidence_status"] == "verified"
                                                      and len(e["content"].strip()) >= 12],
                  "future_requirement_candidates": [{"text": fb["content"], "event_id": fb["event_id"],
                                                      "category": fb["feedback_category"]}],
                  "supporting_event_ids": [fb["event_id"]],
                  "later_revision_sha": following[fb["event_id"]],
                  "possible_later_revision_sha": possible_following[fb["event_id"]],
                  "possible_revision_note": "Later review references a later PR commit; exact push time and causal link remain unverified",
                  "historical_state_confidence": state_confidence,
                  "historical_grounding": grounded, "contextual_inferability": inferable,
                  "action_relevance": relevant,
                  "possible_leakage": bool(pr.get("body") or pr.get("title")),
                  "leakage_note": "Current PR title/body excluded from verified historical context; edits are not versioned here",
                  "status": "provisional", "acceptance_reasons": ["human feedback", "identifiable reviewed/visible commit"],
                  "rejection_reasons": [] if verified_context else ["no verified dated task text before feedback"],
                  "future_feedback_event_id": fb["event_id"],
                  "context_preview": re.sub(r"\s+", " ", verified_context).strip()[:500].rstrip(),
                  "future_preview": re.sub(r"\s+", " ", fb["content"]).strip()[:500].rstrip(),
                  "future_source_url": fb["source_url"],
                  "earlier_source_urls": [e["source_url"] for e in earlier if e["event_id"] in earlier_ids
                                          and e.get("source_url")][:10],
                  "lexical_overlap": overlap}
        cutoffs.append(cutoff)
    cutoffs.sort(key=lambda c: (bool(c["context_preview"]), bool(c["later_revision_sha"]),
                                c["contextual_inferability"] == "possible", c["lexical_overlap"]), reverse=True)
    cutoffs = cutoffs[:cfg["max_cutoffs_per_pr"]]
    for i, cutoff in enumerate(cutoffs):
        cutoff["rank"] = i + 1
        cutoff["best"] = i == 0
    duration = (_dt(pr["merged_at"]) - _dt(pr["created_at"])).total_seconds() / 86400 if pr.get("merged_at") else None
    first_feedback_time = min((e["timestamp"] for e in feedback), default=pr.get("merged_at"))
    dated_context = [e for e in events if e["event_type"] in COMMENT_TYPES and e["actor_type"] == "human"
                     and e["evidence_status"] == "verified" and first_feedback_time
                     and e["timestamp"] < first_feedback_time]
    features = {"repository": data["repository"], "pr_number": pr["number"], "url": pr["html_url"],
                "total_comments": len(comments), "human_comments": len(human),
                "bot_comments": sum(e["actor_type"] == "bot" for e in comments),
                "human_reviewer_comments": len(reviewer),
                "distinct_human_participants": len({e["actor"] for e in human if e["actor"]}),
                "distinct_human_reviewers": len({e["actor"] for e in reviewer if e["actor"]}),
                "review_rounds": review_rounds,
                "change_requested_reviews": sum(e.get("review_state") == "CHANGES_REQUESTED" for e in reviews),
                "author_reviewer_cycles": sum(bool(x) for x in following.values()),
                "commits": len(commits), "changed_files": pr.get("changed_files"),
                "commit_list_complete": data.get("evidence_limits", {}).get("commits_complete"),
                "file_list_complete": data.get("evidence_limits", {}).get("files_complete"),
                "additions": pr.get("additions"), "deletions": pr.get("deletions"),
                "development_duration_days": duration,
                "observable_code_revisions": len(visible_commits),
                "revisions_following_feedback": len(set(x for x in following.values() if x)),
                "feedback_to_revision_sequences": sum(bool(x) for x in following.values()),
                "possible_feedback_to_revision_sequences": sum(bool(x) for x in possible_following.values()),
                "initial_task_description_available": bool(pr.get("title") or pr.get("body")),
                "initial_task_temporally_verified": False,
                "meaningful_history_before_feedback": bool(dated_context and commits),
                "candidate_cutoff_identifiable": bool(cutoffs),
                "historical_commit_sha_available": bool(cutoffs),
                "cutoff_code_state_recoverable": bool(cutoffs),
                "later_human_requirements": bool(feedback),
                "future_requirement_linked_to_context": any(c["contextual_inferability"] == "possible" for c in cutoffs),
                "future_information_leakage_risk": bool(pr.get("body") or pr.get("title")),
                "substantive_feedback_candidates": len(feedback_candidates),
                "substantive_later_feedback_candidates": len(feedback),
                "candidate_future_intents": len(cutoffs), "valid_cutoff_candidates": len(cutoffs),
                "linked_issue_count": len(data["linked_issues"]),
                "feedback_categories": dict(Counter(e["feedback_category"] for e in feedback))}
    reasons = []
    if not feedback:
        reasons.append("NO_SUBSTANTIVE_HUMAN_FEEDBACK_DETECTED")
    if not cutoffs:
        reasons.append("NO_VERIFIED_CUTOFF_COMMIT")
    if cutoffs and not cutoffs[0]["context_preview"]:
        reasons.append("NO_VERIFIED_EARLIER_TASK_TEXT")
    if cutoffs and not cutoffs[0]["later_revision_sha"]:
        reasons.append("POSSIBLE_BUT_UNVERIFIED_REVISION" if cutoffs[0]["possible_later_revision_sha"]
                       else "NO_VERIFIED_POST_FEEDBACK_REVISION")
    if cutoffs and cutoffs[0]["contextual_inferability"] != "possible":
        reasons.append("INFERABILITY_UNCERTAIN")
    if cutoffs and not reasons:
        label = "A"
    elif cutoffs or feedback:
        label = "B"
    else:
        label = "C"
    features["provisional_label"] = label
    features["reason_codes"] = reasons
    return features, cutoffs, [{"repository": data["repository"], "pr_number": pr["number"],
                                "cutoff_timestamp": c["cutoff_timestamp"], "commit_sha": c["commit_sha"],
                                "feedback_event_id": c["future_feedback_event_id"],
                                "category": c["future_requirement_candidates"][0]["category"],
                                "historical_grounding": c["historical_grounding"],
                                "contextual_inferability": c["contextual_inferability"],
                                "action_relevance": c["action_relevance"],
                                "classification_status": "heuristic_unverified"} for c in cutoffs]
