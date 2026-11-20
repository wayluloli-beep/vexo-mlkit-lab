# Aura Sync: Google Cloud Text-to-Speech backend

This is an optional backend for the Vexo Android app. The Android APK **must never**
contain Google Cloud service-account JSON or OAuth access tokens.

## Auth and Google requirements

- Google Cloud project with **Cloud Text-to-Speech API**, **Cloud Run**, billing, and a
  restricted Cloud Run service account authorized to synthesize speech.
- Firebase project linked to the same Google Cloud project; Android application
  registered with **Firebase App Check (Play Integrity)**.
- The mobile client sends the App Check token in the X-Firebase-AppCheck header.
  The server rejects requests unless Firebase Admin verifies it.
- Configure a billing budget and TTS API quotas. The 10/min/token limit here is
  **in-memory per container**, insufficient as a production quota on its own.
  Apply Cloud Armor/rate-limits, abuse monitoring, min/max instances and budget alerts.
- Do not publish the endpoint until App Check enforcement and access limits are tested
  with the correctly signed Play-distributed app.

## API

POST /v1/aura/voice
Headers: Content-Type: application/json; X-Firebase-AppCheck: <token>
Body: {"kind":"intro"} or {"kind":"offer_metrics","perKmCents":340,"perHourCents":4500}
Success: audio/mpeg bytes
Failure: JSON {error:"..."}

No arbitrary input text or screen content is accepted. Offer figures are always sent
as integer cents; native app must only call the metric path after a real validated
offer. Server validates bounds but cannot independently verify a driver's offer.

## Google voice

Default: pt-BR-Chirp3-HD-Achernar (female, Brazilian Portuguese), MP3.
Authentication uses Application Default Credentials on Cloud Run.

## Deploy (only after Firebase App Check is configured)

From this folder, with the Google Cloud CLI authenticated:

    gcloud run deploy vexo-aura-voice --source . \
       --region southamerica-east1 \
       --service-account SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com \
       --allow-unauthenticated --max-instances 2

The public Cloud Run URL accepts only authenticated App Check requests, but
allow-unauthenticated is still a public network exposure. Never deploy before
verifying App Check, quotas and abuse limits.

## Testing

    npm test

Tests mock both Firebase verification and Google's API. They do not create paid
Cloud TTS requests. End-to-end Google voice requires an authorized Cloud account.

## Data/privacy

This backend accepts only event kind and validated numeric metrics. It receives no
screen captures, passengers' information, addresses, or raw recognized text.
Server avoids logging speech or tokens. Audio is not stored.
