"""Business rules and deterministic guardrail rules.

Code enforces these rules. Prompts may describe them, but never enforce them.
These functions only read data. They never write.
"""

import re
from datetime import date

from . import db

# Policy constants. tests/test_tools.py checks that the policy docs say the same.
RETURN_WINDOW_DAYS = 10
DEFECTIVE_WINDOW_DAYS = 10
APPROVAL_THRESHOLD_USD = 100
FREE_SHIPPING_ABOVE_USD = 50
SHIPPING_FEE_USD = 5
PAY_LATER_LIMIT_USD = 1000
MIN_DEFECT_REASON_CHARS = 10

# Counted from the moment the refund is processed.
REFUND_TIMELINES = {
    "card": "5–7 business days",
    "PayPal": "2–3 business days",
    "bank transfer": "3–5 business days",
    "pay later": "7 business days (your remaining payments are adjusted)",
}


def days_since_delivery(order, today=None):
    delivered = date.fromisoformat(order["delivered_date"])
    return ((today or date.today()) - delivered).days


def return_eligibility(customer_id, order_id):
    """Return and defective-refund eligibility for one order.

    Returns None if the order does not exist for this customer.
    return_status is never plain "eligible": the original-box condition
    cannot be known from data, so the best case is "eligible_if_original_box".
    """
    order = db.get_order(customer_id, order_id)
    if order is None:
        return None
    result = {
        "order_id": order["order_id"],
        "return_status": "not_eligible",
        "defective_status": "not_applicable",
        "reason": "",
        "days_since_delivery": None,
        "days_remaining": 0,
    }
    if order["status"] != "delivered":
        result["reason"] = f"the order is '{order['status']}', not delivered"
        return result
    if any(not item["returnable"] for item in db.get_order_items(order["order_id"])):
        result["reason"] = "gift cards are non-returnable"
        return result

    days = days_since_delivery(order)
    result["days_since_delivery"] = days
    if days > RETURN_WINDOW_DAYS:
        result["reason"] = (
            f"delivered {days} days ago; the return window is {RETURN_WINDOW_DAYS} days"
        )
        result["defective_status"] = "defective_refund_window_closed"
        return result

    result["return_status"] = "eligible_if_original_box"
    result["defective_status"] = "defective_refund_window_open"
    result["days_remaining"] = RETURN_WINDOW_DAYS - days
    return result


def validate_refund(customer_id, order_id, refund_type, amount_usd, reason, box_confirmed):
    """Check a refund request. Returns a list of failure reasons. An empty list means ok."""
    order = db.get_order(customer_id, order_id)
    if order is None:
        return ["Order not found for this account."]

    problems = []
    if order["status"] != "delivered":
        problems.append(f"The order is '{order['status']}', not delivered.")
    if db.get_processed_refund(order["order_id"]):
        problems.append("This order already has a processed refund. Only one refund per order.")
    if not isinstance(amount_usd, int) or amount_usd <= 0:
        problems.append("The refund amount must be a positive whole number of dollars.")
    elif amount_usd > order["total_usd"]:
        problems.append(f"The refund amount exceeds the order total of ${order['total_usd']:,}.")
    if any(not item["returnable"] for item in db.get_order_items(order["order_id"])):
        problems.append("Gift cards are non-returnable and cannot be refunded.")
    if not reason or not reason.strip():
        problems.append("A reason is required.")

    within_window = (
        order["delivered_date"] is not None
        and days_since_delivery(order) <= RETURN_WINDOW_DAYS
    )
    if refund_type == "return":
        if order["delivered_date"] and not within_window:
            problems.append(
                f"The {RETURN_WINDOW_DAYS}-day return window has passed."
            )
        if not box_confirmed:
            problems.append(
                "Returns require the item to be unused and in its original box. "
                "Ask the customer to confirm this first."
            )
    elif refund_type == "defective":
        if order["delivered_date"] and not within_window:
            problems.append(
                f"The {DEFECTIVE_WINDOW_DAYS}-day defective-on-arrival window has passed. "
                "This must be a warranty claim (repair or replacement), not a refund."
            )
        if len((reason or "").strip()) < MIN_DEFECT_REASON_CHARS:
            problems.append("Please describe the defect (at least 10 characters).")
    else:
        problems.append("refund_type must be 'return' or 'defective'.")
    return problems


# ---------------------------------------------------------------------------
# Deterministic guardrail rules (used by the guardrail nodes in the notebook)
# ---------------------------------------------------------------------------

INJECTION_PATTERNS = [
    r"system\s+override",
    r"admin\s+mode",
    r"ignore\s+(?:all\s+|any\s+|previous\s+|prior\s+)+instructions",
    r"skip\s+(?:the\s+)?(?:manager\s+)?approval",
    r"reveal\s+your\s+(?:system\s+)?prompt",
]


def flag_injection(text):
    """Return the first injection pattern found in text, or None."""
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# An optional +country code and (area code), then 2 or 3 groups of digits.
# Examples: "+44 7700 900101", "+1 212 555 0102", "(416) 555-0103", "2025550143".
PHONE_RE = re.compile(
    r"(?<![\w+])(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,5}\)[\s-]?)?\d{2,5}(?:[\s-]?\d{2,5}){1,2}(?!\w)"
)
MIN_PHONE_DIGITS = 9  # shorter digit groups are dates or amounts, not phone numbers


def _digits(phone):
    """The last 9 digits, so a number matches with or without its country code."""
    return re.sub(r"\D", "", phone)[-9:]


def mask_contact_details(text, allowed=()):
    """Mask phone numbers and emails, except the ones listed in allowed."""
    allowed_emails = {a.lower() for a in allowed if "@" in a}
    allowed_phones = {_digits(a) for a in allowed if "@" not in a}

    def mask_email(m):
        return m.group(0) if m.group(0).lower() in allowed_emails else "[email hidden]"

    def mask_phone(m):
        number = m.group(0)
        if len(re.sub(r"\D", "", number)) < MIN_PHONE_DIGITS:
            return number
        return number if _digits(number) in allowed_phones else "[phone hidden]"

    return PHONE_RE.sub(mask_phone, EMAIL_RE.sub(mask_email, text))
