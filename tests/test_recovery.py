import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recovery import CUSTOMERS, Ledger, RecoveryError
from assistant import config
from server import create_server
from demo import run


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.token = self.ledger.start("C001", "rehearsal")["token"]

    def verify(self):
        return self.ledger.tool(self.token, "verify_demo_identity", {"demo_code": "DEMO-001"}, "verify")

    def action(self, action, consent=True, ident="action"):
        return self.ledger.tool(self.token, "record_recovery_action", {"action": action, "consent": consent}, ident)

    def test_exactly_ten_fictional_records_without_phone_numbers(self):
        self.assertEqual(len(CUSTOMERS), 10)
        self.assertEqual(len({c["id"] for c in CUSTOMERS}), 10)
        self.assertTrue(all("phone" not in c and "email" not in c for c in CUSTOMERS))

    def test_identity_gate(self):
        self.assertNotIn("payment", self.ledger.view(self.token))
        with self.assertRaises(RecoveryError):
            self.action("retry")
        self.verify()
        self.assertEqual(self.ledger.view(self.token)["payment"]["amount_paise"], 149900)

    def test_failed_identity_and_attempt_limit(self):
        for i in range(3):
            result = self.ledger.tool(self.token,"verify_demo_identity",{"demo_code":"WRONG"},str(i))
            self.assertFalse(result["ok"])
        with self.assertRaises(RecoveryError):
            self.verify()
        self.assertNotIn("payment", self.ledger.view(self.token))

    def test_consent_is_required(self):
        self.verify()
        with self.assertRaises(RecoveryError):
            self.action("retry",False)
        self.assertEqual(self.ledger.view(self.token)["state"], "ready")

    def test_retry_is_not_recovered_until_settlement(self):
        self.verify()
        result = self.action("retry")
        self.assertEqual(result["state"], "retry_queued")
        with self.assertRaises(RecoveryError):
            self.ledger.settle(self.token,"wrong-ref")
        self.assertEqual(self.ledger.settle(self.token,"mock-retry")["state"], "recovered")
        self.ledger.settle(self.token,"mock-retry")
        self.assertEqual(sum(e["type"] == "mock_payment_settled" for e in self.ledger.view(self.token)["events"]), 1)

    def test_duplicate_tool_delivery_is_idempotent(self):
        self.verify()
        first = self.action("retry")
        self.assertEqual(self.action("retry"),first)
        with self.assertRaises(RecoveryError):
            self.action("checkout")
        self.assertEqual(sum(e["type"] == "action_recorded" for e in self.ledger.view(self.token)["events"]),1)

    def test_reverification_does_not_reopen_a_pending_retry(self):
        self.verify()
        self.action("retry")
        self.ledger.tool(self.token,"verify_demo_identity",{"demo_code":"DEMO-001"},"verify-again")
        with self.assertRaises(RecoveryError):
            self.action("retry",ident="second-retry")

    def test_ineligible_mandate_requires_checkout(self):
        self.token = self.ledger.start("C003","rehearsal")["token"]
        self.ledger.tool(self.token,"verify_demo_identity",{"demo_code":"DEMO-003"},"verify")
        with self.assertRaises(RecoveryError):
            self.action("retry")
        result = self.action("checkout",ident="checkout")
        self.assertEqual(result["state"],"checkout_created")
        self.assertEqual(self.ledger.settle(self.token,result["checkout_ref"])["state"],"recovered")

    def test_opt_out_before_identity_and_suppresses_future_sessions(self):
        self.assertEqual(self.action("opt_out")["state"],"opted_out")
        with self.assertRaises(RecoveryError):
            self.ledger.start("C001","vapi")
        with self.assertRaises(RecoveryError):
            self.verify()

    def test_payment_claim_and_dispute_never_confirm_recovery(self):
        for action in ("payment_claim","dispute","callback"):
            ledger = Ledger()
            token = ledger.start("C001","rehearsal")["token"]
            ledger.tool(token,"verify_demo_identity",{"demo_code":"DEMO-001"},"verify")
            result = ledger.tool(token,"record_recovery_action",{"action":action,"consent":True},"action")
            self.assertNotEqual(result["state"],"recovered")
            with self.assertRaises(RecoveryError):
                ledger.settle(token,"mock-retry")

    def test_invalid_token_unknown_tool_and_arguments(self):
        for token, name, args in (("bad","verify_demo_identity",{}),(self.token,"charge_card",{}),
                                  (self.token,"record_recovery_action",{"action":"retry","consent":"yes"}),
                                  (self.token,"verify_demo_identity",{"demo_code":"DEMO-001","card":"x"})):
            with self.assertRaises(RecoveryError):
                self.ledger.tool(token,name,args,"test")

    def test_browser_reported_call_is_not_provider_attested(self):
        token = self.ledger.start("C002","vapi")["token"]
        result = self.ledger.live_event(token,"fictional-call-id")
        self.assertFalse(result["events"][-1]["provider_verified"])
        with self.assertRaises(RecoveryError):
            self.ledger.live_event(self.token,"fake-call")

    def test_assistant_does_not_receive_records_or_credentials(self):
        assistant = config()
        serialized = json.dumps(assistant)
        for customer in CUSTOMERS:
            self.assertNotIn(customer["demo_code"],serialized)
            self.assertNotIn(customer["name"],serialized)
        self.assertNotIn("apiKey",serialized)
        self.assertTrue(all(tool["async"] and "server" not in tool for tool in assistant["model"]["tools"]))


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:"+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def test_blocks_cross_origin_and_dns_rebinding(self):
        for headers in ({"Origin":"https://attacker.example"},{"Host":"attacker.example"}):
            with self.assertRaises(HTTPError) as caught:
                urlopen(Request(self.base+"/api/customers",headers=headers),timeout=3)
            self.assertEqual(caught.exception.code,403)

    def test_static_allowlist_does_not_expose_project_files(self):
        for path in ("/../.env","/customers.json","/server.py","/.git/config"):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.base+path,timeout=3)
            self.assertEqual(caught.exception.code,404)

    def test_json_input_limit(self):
        request = Request(self.base+"/api/session",data=b"x"*16001,headers={"Content-Type":"application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request,timeout=3)
        self.assertEqual(caught.exception.code,400)

    def test_serves_browser_and_exactly_ten_records(self):
        with urlopen(self.base+"/api/customers",timeout=3) as response:
            self.assertEqual(len(json.load(response)["customers"]),10)
        with urlopen(self.base,timeout=3) as response:
            self.assertIn(b"Recovery outcome",response.read())


class EndToEndTests(unittest.TestCase):
    def test_all_ten_http_scenarios(self):
        report = run()
        self.assertEqual(report["customers"],10)
        self.assertEqual(report["simulated_recovered_count"],5)
        self.assertFalse(report["live_provider_used"])


if __name__ == "__main__":
    unittest.main()
