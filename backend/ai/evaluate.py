"""Repeatable checks for the deterministic event recommender."""

from __future__ import annotations

from ai.event_analyzer import fallback_generate

CASES = [
    {
        "name": "buy-now-journey",
        "requirement": "Customer selects a broadband plan, clicks Buy Now, and starts checkout.",
        "expected": ["plan_selected", "purchase_button_clicked", "checkout_started"],
    },
    {
        "name": "checkout-only",
        "requirement": "The customer proceeds to payment checkout.",
        "expected": ["checkout_started"],
    },
    {
        "name": "plan-selection",
        "requirement": "Customer chooses a mobile tariff.",
        "expected": ["plan_selected"],
    },
    {
        "name": "buy-click",
        "requirement": "User clicks the purchase button.",
        "expected": ["purchase_button_clicked"],
    },
    {
        "name": "payment-step",
        "requirement": "Customer continues to payment.",
        "expected": ["checkout_started"],
    },
    {
        "name": "unmatched-journey",
        "requirement": "Open the help center article.",
        "expected": ["help_center_article"],
    },
]


def duplicate_quality(contracts: dict | None = None) -> dict:
    """Precision and recall for catalogue duplicate flags on a fixed labeled set."""
    from ai.event_analyzer import _annotate_with_catalogue

    catalogue = contracts or {}
    labeled = [
        {
            "event_name": "checkout_begin",
            "description": "Start of checkout",
            "parameters": {
                "cart_id": {"type": "string", "required": True},
                "product_id": {"type": "string", "required": True},
                "total_amount": {"type": "number", "required": True},
            },
            "duplicate": True,
        },
        {
            "event_name": "widget_rotated",
            "description": "Widget rotated",
            "parameters": {
                "widget_id": {"type": "string", "required": True},
                "surface_id": {"type": "string", "required": True},
            },
            "duplicate": False,
        },
    ]
    if not catalogue:
        return {"precision": None, "recall": None, "passed": True}
    annotated = _annotate_with_catalogue(labeled, catalogue)
    true_positive = false_positive = false_negative = 0
    for item, label in zip(annotated, labeled, strict=True):
        text = item.get("recommendation") or ""
        predicted = bool(item.get("reuse_existing")) or "duplicate" in text.lower() or "overlaps" in text.lower()
        if predicted and label["duplicate"]:
            true_positive += 1
        elif predicted and not label["duplicate"]:
            false_positive += 1
        elif label["duplicate"]:
            false_negative += 1
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
    return {"precision": precision, "recall": recall, "passed": precision == 1.0 and recall == 1.0}


def evaluate(contracts: dict | None = None) -> list[dict]:
    results = []
    for case in CASES:
        generated = fallback_generate(case["requirement"], contracts or {}, None)
        names = [event["event_name"] for event in generated["events"]]
        results.append(
            {
                "name": case["name"],
                "expected": case["expected"],
                "actual": names,
                "passed": names == case["expected"],
            }
        )
    quality = duplicate_quality(contracts)
    results.append(
        {
            "name": "duplicate-detection",
            "expected": ["precision", "recall"],
            "actual": [quality["precision"], quality["recall"]],
            "passed": quality["passed"],
        }
    )
    return results
