"""Exercise all ten fictional recovery paths through the actual local HTTP API."""
import json
import threading
from urllib.request import Request, urlopen
from server import create_server
from recovery import CUSTOMERS


def run():
    server = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(server.server_port)
    def post(path, body):
        request = Request(base + "/api/" + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    results = []
    try:
        for customer in CUSTOMERS:
            session = post("session", {"customer_id": customer["id"], "mode": "rehearsal"})
            token = session["token"]
            assert "payment" not in session
            if customer["scenario"] != "wrong_person":
                verified = post("tool", {"token": token, "name": "verify_demo_identity",
                                "arguments": {"demo_code": customer["demo_code"]}, "tool_call_id": "verify"})
                assert verified["ok"]
            action = customer["scenario"]
            payload = {"token": token, "name": "record_recovery_action",
                       "arguments": {"action": action, "consent": True}, "tool_call_id": "action"}
            result = post("tool", payload)
            assert post("tool", payload) == result  # Duplicate delivery is safe.
            if action in ("retry", "checkout"):
                assert result["state"] != "recovered"
                state = post("settle", {"token": token, "reference": result["checkout_ref"] or "mock-retry"})
                assert state["state"] == "recovered"
            else:
                state = post("state", {"token": token})
                assert state["state"] != "recovered"
            if action == "wrong_person":
                assert "payment" not in state
            results.append({"customer_id": customer["id"], "scenario": action, "outcome": state["state"],
                            "simulated_recovered_paise": customer["amount_paise"] if state["state"] == "recovered" else 0})
        report = {"mode": "offline_http_rehearsal", "live_provider_used": False, "fictional": True,
                  "customers": len(results), "results": results,
                  "simulated_recovered_count": sum(r["outcome"] == "recovered" for r in results),
                  "simulated_recovered_paise": sum(r["simulated_recovered_paise"] for r in results)}
        print(json.dumps(report, indent=2))
        print("PASS: ten HTTP recovery scenarios; NOT a live voice-provider demonstration")
        return report
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    run()
