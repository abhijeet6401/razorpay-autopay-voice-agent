# Cedar · Voice agent for autopay recovery

Razorpay Forward-Deployed Engineer assignment, **option 2**. Ten fictional customer records, an empathetic Vapi browser voice agent, and a deterministic mock payment backend.

**Current verification:** the official Vapi Web SDK 2.7.1 builds successfully, 18 automated tests pass, all ten recovery scenarios run through the real local HTTP API, and the browser rehearsal was manually exercised through identity, retry and simulated settlement. **A live Vapi voice conversation has not yet been run**, because a provider account/public key is not available. The offline rehearsal is not sufficient by itself to claim the assignment's provider-based end-to-end demonstration is complete. Follow the live run steps below, capture provider evidence, then submit.

No number is dialed. The tester speaks through their own microphone. No real payment is attempted, no SMS/email is sent, and all customer records are explicitly fictional. There are no phone numbers in the dataset.

## Run locally

Requires Python 3.10+ for the server and Node.js 18+ for the browser bundle. No Python dependencies.

```sh
# From the project folder containing this README:
npm ci
npm run build
python server.py
```

Open [the local demo](http://127.0.0.1:8765). On Windows, `run.ps1 serve` finds Python on PATH or the bundled Codex runtime. The bundle is generated locally and ignored by Git; npm's lockfile pins dependencies. It is also included in the local submission ZIP so the ZIP can run without Node. Source check: `npm run check`.

The **Rehearsal** tab works without npm, an account or a key:

```sh
python demo.py
python -m unittest discover -s tests -v
```

The command-line demo executes all ten HTTP scenarios with scripted actions and verifies duplicate-delivery safety. The UI uses scripted response buttons in rehearsal, not speech recognition or an LLM. Neither rehearsal path counts as a live provider call.

## Connect Vapi and run the actual voice demo

1. Create/sign in to your [Vapi dashboard](https://dashboard.vapi.ai). Any account terms, credits or billing are for you to review. This project does not create accounts or purchase credits.
2. Create a **public browser API key**. Restrict allowed origins to `http://127.0.0.1:8765` (or the exact localhost origin you use). Enable transient assistants for this demo, because the app passes the assistant configuration at call start. The model, voice and transcriber must be available in your Vapi account; adjust `assistant.py` if the provider reports an unsupported combination.
3. Open the local UI, choose a customer, then **Live browser voice**. Paste the Vapi public key into the local field. It stays in page/SDK memory, is cleared from the field at call start, and is never sent to this Python backend, saved to disk, exported or committed. Do not enter a Vapi private key or an OpenAI key. The selected OpenAI model is used through Vapi's account configuration; no separate OpenAI key is requested by this app.
4. Agree to share your microphone audio and fictional conversation data with Vapi, click **Start voice conversation**, and allow browser microphone access. Internet access and sufficient provider credits are required. Costs/retention depend on the provider account; no specific free allowance is assumed.
5. Role-play as Asha. Say it is a good time, give the fictional `DEMO-001` identifier, ask about the failed payment, then explicitly consent to a mock retry. The backend must show `retry queued`, not recovered.
6. Click **Complete fictional payment**. This separate mock settlement is not an agent tool. The UI changes to recovered and sends an authoritative local-backend message to the ongoing voice conversation. The agent should acknowledge only simulated recovery.
7. End the call, export evidence and locate the matching call ID in the Vapi dashboard. Repeat with an expired/revoked mandate and an opt-out or already-paid scenario. To reset opt-out suppression and all fictional data, restart the Python server.

Do not use real customer identities or payment details during this demonstration. Browser-mode tooling is trusted only for this local fictional demo, not real collections.

## What the agent does

- Discloses that it is an AI and asks whether it is a good time.
- Verifies a **fictional role-play identifier**, not an OTP or production identity check, before receiving amount or failure reason.
- Offers a mock retry only for an active mandate with insufficient funds/bank-unavailable failure and explicit consent.
- Offers fictional checkout for revoked/expired mandates or authorization-required failures. Checkout does not renew a mandate.
- Records callbacks, disputes and payment claims for follow-up without pretending they are scheduled, resolved or paid.
- Accepts opt-out and wrong-person reports before identity verification and suppresses later sessions for that customer during this server process.
- Never requests card data, PINs, OTPs or passwords, and never promises recovery before a separate settlement event.

Two Vapi asynchronous client tools dispatch to the loopback API: `verify_demo_identity` and `record_recovery_action`. Vapi client-side tools do not return synchronous model results. The browser calls the backend, then uses the installed SDK's `send({type:'add-message', ...})` API to inject `LOCAL_BACKEND_RESULT` system context and trigger a response. The prompt instructs the agent to wait for this context. This live timing must be verified in a real call; rehearsal tests cannot validate an LLM's compliance.

## Architecture

```text
Tester microphone <-> Vapi speech/model/voice pipeline
                           |
                   browser tool-calls event
                           |
Browser UI --------> loopback Python backend --------> in-memory fictional ledger
    |                     identity + consent gates
    +---- backend result injected into Vapi conversation

Tester UI ---------> separate mock settlement event -> simulated recovery
```

The assistant starts without any selected record, demo identifier, amount or customer name. Verification returns only the selected session's payment facts. A random session capability binds tools to one customer, and call IDs deduplicate actions. Endpoint allowlisting, local Host/Origin validation, a 16 KB request limit, sanitized failures and text-only rendering limit accidental exposure. Private keys are unnecessary and unsupported.

## The ten cases

| Customer | Failure | Expected path |
| --- | --- | --- |
| C001 Asha | Insufficient funds, active | Consent → queued mock retry → separate mock settlement |
| C002 Kabir | Bank unavailable, active | Same retry path |
| C003 Meera | Mandate revoked | Fictional checkout; no mandate renewal |
| C004 Dev | Mandate expired | Fictional checkout; no mandate renewal |
| C005 Tara | Authorization required | Fictional checkout |
| C006 Ishan | Insufficient funds | Callback requested; no call scheduled |
| C007 Leela | Bank unavailable | Opt out; further sessions suppressed |
| C008 Rohan | Insufficient funds | Already-paid claim; needs reconciliation |
| C009 Nila | Authorization required | Disputed; human review |
| C010 Arjun | Bank unavailable | Wrong person; no payment disclosure |

The scripted run reports five **simulated** recoveries totaling ₹6,695. This describes the fixture outcomes, not a real recovery rate or revenue result.

## Evidence and submission

`demo-output.txt` and `verification.txt` capture the offline HTTP exercise and test results. UI exports include mode, fictional ledger events, transcript and provider call ID when available. They never include API keys or the session capability. The browser's provider events are **not server-attested**; compare the ID with Vapi's call log and capture a short screen recording of the actual voice conversation for the hiring team. Keep personal speech out of shared recordings.

Use `LIVE_DEMO_CHECKLIST.md` to verify the voice call before claiming end-to-end provider completion. The checklist is currently unchecked. `package_submission.py` builds `voice-submission.zip` from an explicit file allowlist; it does not include credentials, node_modules or unreviewed live exports.

## Limits and production changes

This is a single-tester local demo. Sessions, suppression and ledger reset when the process restarts. Callback means a request, not a scheduler. Checkout is an on-screen simulation, not a payment link sent to the customer. Rehearsal amounts/state are deterministic. Voice responses are model-generated and may vary. Exported transcripts and live call IDs need provider verification. There is no real autopay processor, mandate renewal, payment webhook, PSTN dialing, human transfer or durable audit database.

For production, move action tools to authenticated server-side webhooks, use real customer authentication outside the model, durable tenant/customer suppression, trusted payment-provider settlement webhooks, signed callback validation, an idempotent payment gateway integration, consent records and approved contact policies. Validate language, interruptions, latency, incorrect identity, tool timeouts and opt-outs across real provider calls. This project does not claim legal, regulatory or payment compliance.

## Official references

- [Vapi web calls](https://docs.vapi.ai/quickstart/web)
- [Vapi browser client-side tools and their result limitation](https://docs.vapi.ai/tools/client-side-websdk)
- [Vapi public-key restrictions](https://docs.vapi.ai/security-and-privacy/api-keys)
- [Official Web SDK source](https://github.com/VapiAI/client-sdk-web)

The implementation was checked against installed SDK 2.7.1. Documentation calls context injection `addMessage`; this installed SDK exposes it through `send` with an `add-message` envelope.
