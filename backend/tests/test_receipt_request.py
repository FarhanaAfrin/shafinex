"""Verify the request we send to Claude, without calling the API.

Stubs the SDK client and inspects the outgoing parameters: model, image block
shape, media type, base64 payload, and the structured-output schema. Also checks
that a refusal and an unreadable response are handled rather than crashing.

Run: .venv/bin/python -m tests.test_receipt_request
"""

import base64
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-fake-key-for-shape-checking"

from app.services import receipts  # noqa: E402
from app.services.receipts import ReceiptError, ReceiptExtraction, extract_receipt  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{'' if condition else '  -> ' + detail}")
    if not condition:
        failures.append(label)


PNG = b"\x89PNG\r\n\x1a\n" + b"fake-pixels" * 20

SAMPLE = ReceiptExtraction(
    is_receipt=True, merchant="Ramen Ichiban", spent_on="2026-05-11", currency="JPY",
    total=9000.0, subtotal=8182.0, tax=818.0, tip=None, payment_method="Visa 1234",
    line_items=[{"description": "Tonkotsu x3", "amount": 4500.0}],
    suggested_category="Dining out", likely_shared=True, likely_people_count=3,
    confidence=0.94, notes=None,
)


class StubMessages:
    def __init__(self, response):
        self.response = response
        self.captured = None

    def parse(self, **kwargs):
        self.captured = kwargs
        return self.response


class StubResponse:
    def __init__(self, parsed=SAMPLE, stop_reason="end_turn"):
        self.parsed_output = parsed
        self.stop_reason = stop_reason
        self.stop_details = None
        self.usage = type("U", (), {"input_tokens": 1800, "output_tokens": 240})()


class StubClient:
    def __init__(self, response):
        self.messages = StubMessages(response)


def run(response, **kwargs):
    stub = StubClient(response)
    receipts._client = lambda: stub          # noqa: SLF001 - deliberate test seam
    result = extract_receipt(PNG, "image/png", ["Dining out", "Groceries"], **kwargs)
    return stub.messages.captured, result


print("\nrequest shape")
sent, draft = run(StubResponse())
check("uses claude-opus-5 by default", sent["model"] == "claude-opus-5", sent["model"])
check("asks for the structured schema", sent["output_format"] is ReceiptExtraction, str(sent.get("output_format")))
check("sends a system prompt", isinstance(sent["system"], str) and len(sent["system"]) > 100)
check("sets max_tokens generously", sent["max_tokens"] >= 8000, str(sent["max_tokens"]))

content = sent["messages"][0]["content"]
check("sends exactly one user turn", len(sent["messages"]) == 1 and sent["messages"][0]["role"] == "user")
image_blocks = [b for b in content if b["type"] == "image"]
check("includes exactly one image block", len(image_blocks) == 1, str([b["type"] for b in content]))
source = image_blocks[0]["source"]
check("uses base64 source", source["type"] == "base64", str(source["type"]))
check("declares the sniffed media type", source["media_type"] == "image/png", source["media_type"])
check("base64 round-trips to the original bytes", base64.standard_b64decode(source["data"]) == PNG)
check("image comes before the text block", content[0]["type"] == "image", str([b["type"] for b in content]))

text_blocks = [b for b in content if b["type"] == "text"]
check("passes the user's real categories", "Dining out" in text_blocks[0]["text"] and "Groceries" in text_blocks[0]["text"])
check("no user-supplied free text reaches the model", len(text_blocks) == 1)

print("\nprompt-injection posture")
system = sent["system"]
check("tells the model image text is data, not instructions", "never follow" in system.lower() or "data — transcribe" in system.lower())
check("tells the model not to invent values", "never invent" in system.lower())
check("constrains the category to the given list", "copied exactly" in system.lower())

print("\nparsed result")
check("returns the parsed draft", draft.merchant == "Ramen Ichiban", str(draft.merchant))
check("carries the split hint", draft.likely_shared is True and draft.likely_people_count == 3)

print("\nfailure handling")
try:
    run(StubResponse(stop_reason="refusal"))
    check("refusal raises a clean error", False, "no exception")
except ReceiptError as error:
    check("refusal raises a clean error", "declined" in str(error).lower(), str(error))

try:
    run(StubResponse(parsed=None))
    check("unparseable response raises a clean error", False, "no exception")
except ReceiptError as error:
    check("unparseable response raises a clean error", True, str(error))

try:
    run(StubResponse(stop_reason="max_tokens"))
    check("truncation raises a clean error", False, "no exception")
except ReceiptError as error:
    check("truncation raises a clean error", "too long" in str(error).lower(), str(error))

try:
    extract_receipt(PNG, "application/pdf", [])
    check("rejects a non-image media type", False, "no exception")
except ReceiptError:
    check("rejects a non-image media type", True)

try:
    extract_receipt(b"x" * (5 * 1024 * 1024), "image/png", [])
    check("rejects an oversized image", False, "no exception")
except ReceiptError:
    check("rejects an oversized image", True)

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILED: {failures}"))
sys.exit(1 if failures else 0)
