"""Safety checks for what the language model returns."""


def filter_findings(findings, decision_texts):
    """Keep only conflict findings that point at a real stored decision.

    A small local model sometimes invents decision IDs. Findings with an
    unknown ID are dropped, the stored text replaces whatever the model
    echoed back, and the same (old decision, new decision) pair is only
    reported once.

    `decision_texts` maps decision id -> stored decision text.
    """

    valid = []
    seen = set()

    for finding in findings:

        stored_text = decision_texts.get(finding.previous_decision_id)

        if stored_text is None:
            continue

        key = (finding.previous_decision_id, finding.new_decision)

        if key in seen:
            continue

        seen.add(key)

        finding.previous_decision = stored_text
        valid.append(finding)

    return valid
