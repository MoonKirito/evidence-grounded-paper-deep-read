"""Shared, standalone checks for global visual selection and report coverage."""
from __future__ import annotations

import re


def visual_id(item: dict) -> str:
    return f"{item.get('figType', '')} {item.get('name', '')}"


def plan_problems(plan: dict, analysis: dict) -> list[str]:
    problems = []
    source = {visual_id(item): item for item in analysis.get("items", [])}
    items = plan.get("items", [])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        return ["Visual plan items must be a list of objects"]
    if any(not isinstance(item.get("id"), str) for item in items):
        return ["Visual plan IDs must be strings"]
    decisions = {item.get("id"): item for item in items}
    if len(decisions) != len(items) or set(decisions) != set(source):
        problems.append("Visual plan must decide every analyzed figure/table exactly once")
    for identity, decision in decisions.items():
        if identity not in source:
            continue
        original = source[identity]
        include = decision.get("include")
        section = decision.get("section")
        duplicate = decision.get("duplicate_of", "")
        if not isinstance(duplicate, str):
            problems.append(f"Invalid duplicate representative: {identity}")
            duplicate = ""
        if type(include) is not bool or section not in {"what", "why", "how", "experiment", "question", "none"}:
            problems.append(f"Invalid visual decision: {identity}")
        if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
            problems.append(f"Missing visual selection rationale: {identity}")
        topics = decision.get("covers")
        if not isinstance(topics, list) or not all(isinstance(topic, str) and topic.strip() for topic in topics) or (include and not topics):
            problems.append(f"Missing visual coverage topics: {identity}")
        if decision.get("image") != original.get("image", ""):
            problems.append(f"Visual plan changed the extracted image path: {identity}")
        usable = original.get("status") == "analyzed" and bool(original.get("image"))
        if include and (not usable or section == "none" or duplicate):
            problems.append(f"Unavailable/duplicate visual cannot be included: {identity}")
        if duplicate:
            target = decisions.get(duplicate, {})
            if include or not target.get("include") or duplicate == identity:
                problems.append(f"Duplicate must point directly to an included representative: {identity}")
            if original.get("section") == "how" and target.get("section") != "how":
                problems.append(f"Method duplicate must be covered by a How visual: {identity}")
            target_topics = target.get("covers", [])
            if (not isinstance(topics, list) or not topics or not isinstance(target_topics, list)
                    or any(topic not in target_topics for topic in topics)):
                problems.append(f"Duplicate representative does not cover all declared technical topics: {identity}")
        # A single-visual 'selected' recommendation cannot silently suppress a
        # distinct method visual. Global deduplication is the only usable omission.
        if usable and original.get("section") == "how":
            if include and section != "how":
                problems.append(f"Technical-route visual belongs in How: {identity}")
            if not include and not duplicate:
                problems.append(f"Method visual omitted without a duplicate representative: {identity}")
    claims = plan.get("claims")
    if not isinstance(claims, list) or not claims:
        problems.append("Visual plan must map the core paper claims to evidence and presentation choices")
    else:
        for claim in claims:
            if not isinstance(claim, dict):
                problems.append("Invalid claim coverage record")
                continue
            if any(not isinstance(claim.get(key), str) or not claim[key].strip() for key in ("claim", "reason")):
                problems.append("Claim coverage needs a claim and a specific rationale")
            anchors = claim.get("evidence")
            if not isinstance(anchors, list) or not anchors or not all(isinstance(anchor, str) and anchor.strip() for anchor in anchors):
                problems.append("Claim coverage needs real evidence anchors")
            references = claim.get("visuals")
            if not isinstance(references, list) or any(not isinstance(ref, str) or ref not in source for ref in references):
                problems.append("Claim coverage references unknown visuals")
                continue
            if claim.get("presentation") not in {"image", "text"}:
                problems.append("Claim presentation must be image or text")
            if claim.get("presentation") == "image" and not any(decisions.get(ref, {}).get("include") for ref in references):
                problems.append(f"Claim has no selected supporting visual: {claim.get('claim')}")
    return problems


def coverage_problems(text: str, plan: dict) -> list[str]:
    """Check the agreed visual placements; no arbitrary figure-count quota."""
    problems = []
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    headings = list(re.finditer(r"^##\s+\d+\.\s+(What|Why|How|Experiment|Question)\b.*$", prose, re.M | re.I))
    bodies = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(prose)
        bodies[heading.group(1).lower()] = prose[heading.end():end]
    embedded = {path.strip().strip("<>") for path in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", prose)}
    included = set()
    for item in plan.get("items", []):
        if not item.get("include"):
            continue
        path = item.get("image", "")
        included.add(path)
        section = item.get("section")
        body = bodies.get(section, "")
        if path not in {p.strip().strip("<>") for p in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body)}:
            problems.append(f"Planned visual missing from {section}: {item.get('id')}")
    for path in embedded - included:
        problems.append(f"Embedded visual was not approved in the global selection plan: {path}")
    return problems
