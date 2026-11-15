"""Remove explicit denials of specific risk phrases, preserving other clauses."""

import re


def affirmative_text(text):
    sensitive = r"(?:OTP|bank(?: account)? password|ATM PIN|CVV|credit card(?: number)?|net banking password)"
    text = re.sub(
        r"\b(?:never|do not|does not|will not|don't|won't)\s+(?:ask(?: you)?(?: for)?|request|require|share|send)\s+(?:(?:your|a|an|the)\s+)?"
        + sensitive,
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(?:no|without|not)\s+(?:guaranteed?\s+(?:job|placement|selection|visa)|registration fees?|application fees?|security deposits?)",
        "",
        text,
        flags=re.I,
    )
    return text
