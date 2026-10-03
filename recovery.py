"""Deterministic fictional payment ledger. No payment or telephony integration."""
import json
from pathlib import Path
import secrets
import threading
from datetime import datetime, timezone

CUSTOMERS = json.loads(Path(__file__).with_name("customers.json").read_text(encoding="utf-8"))
ACTIONS = ["retry", "checkout", "callback", "dispute", "opt_out", "payment_claim", "wrong_person"]
TERMINAL = {"opted_out", "wrong_person", "disputed", "claimed_paid", "callback_requested", "recovered"}


class RecoveryError(Exception):
    pass


class Ledger:
    def __init__(self):
        self.sessions = {}
        self.suppressed = set()
        self.lock = threading.RLock()

    def start(self, customer_id, mode):
        if mode not in ("rehearsal", "vapi"):
            raise RecoveryError("Invalid mode")
        customer = next((c for c in CUSTOMERS if c["id"] == customer_id), None)
        if not customer:
            raise RecoveryError("Unknown fictional customer")
        with self.lock:
            if customer_id in self.suppressed:
                raise RecoveryError("Customer suppressed after opt-out or wrong-person report; restart only to reset fictional data")
            token = secrets.token_urlsafe(32)
            self.sessions[token] = {"id": secrets.token_hex(8), "customer": customer,
                                    "mode": mode, "verified": False, "state": "unverified",
                                    "checkout_ref": None, "events": [], "dedupe": {}, "live_call_id": None}
            self.event(self.sessions[token], "session_started", {"mode": mode})
            return {"token": token, **self.view(token)}

    def session(self, token):
        if not isinstance(token, str) or token not in self.sessions:
            raise RecoveryError("Invalid session")
        return self.sessions[token]

    @staticmethod
    def event(session, kind, data):
        session["events"].append({"at": datetime.now(timezone.utc).isoformat(), "type": kind, **data})

    def view(self, token):
        session = self.session(token)
        result = {"session_id": session["id"], "customer_id": session["customer"]["id"],
                  "mode": session["mode"], "verified": session["verified"], "state": session["state"],
                  "events": session["events"], "checkout_ref": session["checkout_ref"],
                  "live_call_id": session["live_call_id"], "fictional": True}
        if session["verified"]:
            result["payment"] = {k: session["customer"][k] for k in
                                 ("amount_paise", "currency", "failure_reason", "mandate_status")}
        return result

    def tool(self, token, name, args, tool_id):
        if not isinstance(tool_id, str) or not 1 <= len(tool_id) <= 200:
            raise RecoveryError("A bounded tool call ID is required")
        if not isinstance(args, dict):
            raise RecoveryError("Arguments must be an object")
        with self.lock:
            session = self.session(token)
            signature = json.dumps([name, args], sort_keys=True)
            if tool_id in session["dedupe"]:
                previous, result = session["dedupe"][tool_id]
                if previous != signature:
                    raise RecoveryError("Tool call ID reused with different arguments")
                return result
            if name == "verify_demo_identity":
                if set(args) != {"demo_code"} or not isinstance(args["demo_code"], str):
                    raise RecoveryError("Expected only demo_code")
                if session["state"] in TERMINAL:
                    raise RecoveryError("Session is closed")
                attempts = sum(e["type"] == "identity_rejected" for e in session["events"])
                if attempts >= 3:
                    raise RecoveryError("Identity attempts exhausted; end the conversation")
                if args["demo_code"].strip().upper().replace(" ", "") != session["customer"]["demo_code"]:
                    self.event(session, "identity_rejected", {})
                    result = {"ok": False, "message": "Demo identity did not match. No payment information disclosed."}
                else:
                    if not session["verified"]:
                        session["verified"] = True
                        session["state"] = "ready"
                        self.event(session, "identity_verified", {})
                    result = {"ok": True, "message": "Fictional identity confirmed", "payment": self.view(token)["payment"]}
            elif name == "record_recovery_action":
                if set(args) != {"action", "consent"} or args.get("action") not in ACTIONS or type(args.get("consent")) is not bool:
                    raise RecoveryError("Expected a documented action and boolean consent")
                action = args["action"]
                if session["state"] in TERMINAL:
                    raise RecoveryError("Session is closed")
                if action not in ("opt_out", "wrong_person") and not session["verified"]:
                    raise RecoveryError("Confirm demo identity before any payment action")
                if not args["consent"]:
                    raise RecoveryError("Explicit customer request or consent required")
                if action == "retry":
                    customer = session["customer"]
                    if customer["mandate_status"] != "active" or customer["failure_reason"] not in ("insufficient_funds", "bank_unavailable"):
                        raise RecoveryError("Retry ineligible. Offer fictional checkout without renewing any mandate.")
                    if session["state"] != "ready":
                        raise RecoveryError("A recovery action is already pending")
                    session["state"] = "retry_queued"
                    message = "Mock retry queued. No money moved; recovery has not been confirmed."
                elif action == "checkout":
                    if session["state"] not in ("ready", "checkout_created"):
                        raise RecoveryError("A recovery action is already pending")
                    session["checkout_ref"] = session["checkout_ref"] or secrets.token_hex(12)
                    session["state"] = "checkout_created"
                    message = "Fictional checkout opened in the demo UI. This does not renew an autopay mandate."
                else:
                    session["state"] = {"callback": "callback_requested", "opt_out": "opted_out", "dispute": "disputed",
                                        "payment_claim": "claimed_paid", "wrong_person": "wrong_person"}[action]
                    message = {"callback": "Callback request recorded locally; no call has been scheduled.",
                               "opt_out": "This fictional recovery session is opted out. No further attempt is permitted.",
                               "dispute": "Dispute recorded for human review; no collection action will continue.",
                               "payment_claim": "Payment claim recorded for reconciliation; not confirmed paid.",
                               "wrong_person": "Wrong person recorded; do not disclose payment information."}[action]
                    if action in ("opt_out", "wrong_person"):
                        self.suppressed.add(session["customer"]["id"])
                self.event(session, "action_recorded", {"action": action, "state": session["state"]})
                result = {"ok": True, "message": message, "state": session["state"],
                          "checkout_ref": session["checkout_ref"], "fictional": True}
            else:
                raise RecoveryError("Unknown tool")
            session["dedupe"][tool_id] = (signature, result)
            return result

    def settle(self, token, reference):
        with self.lock:
            session = self.session(token)
            if session["state"] == "recovered":
                return self.view(token)
            valid_retry = session["state"] == "retry_queued" and reference == "mock-retry"
            valid_checkout = session["state"] == "checkout_created" and reference == session["checkout_ref"]
            if not session["verified"] or not (valid_retry or valid_checkout):
                raise RecoveryError("No matching authorized mock payment to settle")
            session["state"] = "recovered"
            self.event(session, "mock_payment_settled", {"amount_paise": session["customer"]["amount_paise"], "fictional": True})
            return self.view(token)

    def live_event(self, token, call_id):
        with self.lock:
            session = self.session(token)
            if session["mode"] != "vapi" or not isinstance(call_id, str) or not 1 <= len(call_id) <= 200:
                raise RecoveryError("Invalid provider call event")
            session["live_call_id"] = call_id
            self.event(session, "browser_reported_provider_call", {"call_id": call_id, "provider_verified": False})
            return self.view(token)
