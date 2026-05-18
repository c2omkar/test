# Devzy demo runbook — audio-driven version

You have the narration audio (~3:45). This guide tells you **what to show on screen and when to click** while the audio plays. Each beat below corresponds to one paragraph of the script with an estimated timestamp.

Estimated voice pace ~150 wpm. Play your MP3 once with a stopwatch before recording to confirm timing — adjust if your voice runs longer or shorter.

---

## Before you hit record (do this 5 min beforehand)

### 1. Pre-flight checks

```bash
cd /Users/omkar.chougale/Uncategorized/DevzySandboxTestingv2

# Backend running?
curl -s http://localhost:3001/healthz | grep ok && echo "backend OK"

# Smee tunnel running, no ECONNREFUSED?  → glance at smee terminal

# ffmpeg available?
which ffmpeg

# Anthropic credit > $1?  → https://console.anthropic.com/settings/billing
```

### 2. Pre-run a demo PR (CRITICAL — gives you a fully-loaded PR for the closing shots)

```bash
./scripts/demo-trigger.sh
```

Note the PR URL it prints (e.g., `https://github.com/omkarc19/devzy-test-app/pull/N`). **Open that URL in a browser tab and keep it open** — by the time you record, all bot comments will be posted on this PR. We'll use it during beats 8–12.

### 3. Arrange your windows

```
┌──────────────────────────┬──────────────────────────┐
│  Browser tab 1: PR list  │  Terminal 1: backend log │
│  Browser tab 2: ★PR-PRE  │  (npm start, idle)       │
│  Browser tab 3: artifacts│                          │
├──────────────────────────┼──────────────────────────┤
│  Terminal 2: project dir │  Terminal 3: smee tunnel │
│  (ready to type)         │  (or hidden)             │
└──────────────────────────┴──────────────────────────┘
```

- **Browser tab 2 (★ PR-PRE)** is the pre-run PR — the one with all comments already posted. This is your "money shot" for beats 8–12.
- **Terminal 2** should already be `cd`'d into the project root. The command `./scripts/demo-trigger.sh` should be in your shell history so you can up-arrow to it (faster than typing).

### 4. Start everything together

1. Open Loom (or QuickTime / Screen Studio) → Start screen recording
2. Hit **Play** on your audio MP3
3. Follow the beats below

---

## Beat-by-beat click guide

### Beat 1 — Intro · 0:00 – 0:20

**Audio:** *"Hi, this is Devzy — a service that runs your pull requests in real sandbox environments and validates them with AI-generated tests. I'll show you the whole flow end to end in under four minutes."*

**On screen:** Terminal 1 (backend log, idle — just `devzy backend listening on :3001 mode=github`)

**Action:** None. Just stay on the backend terminal showing the idle state.

**Why:** Sets the stage — viewer sees the running system before any action.

---

### Beat 2 — The problem · 0:20 – 0:42

**Audio:** *"When a developer pushes a PR, most teams either wait minutes for staging or burn engineering time spinning up an environment manually. Devzy does it automatically, in under 90 seconds — sandbox, full test run, AI-generated tests, and a screen recording of the user journey — all posted back to the PR."*

**On screen:** Optional — switch briefly to **Browser tab 1 (PR list)** to show past PRs with green checks. Or stay on the terminal.

**Action:** None (or one window switch).

---

### Beat 3 — Set up the role-play · 0:42 – 0:56

**Audio:** *"Let me show you. I'm going to play the role of a developer who just added a new feature: a 'clear all visits' endpoint with a button to use it. I run one command."*

**On screen:** Switch to **Terminal 2** (the project-dir terminal, ready to type).

**Action:** Bring the terminal to focus. Cursor positioned at the prompt. **Do not type yet** — wait until beat 4.

---

### Beat 4 — Run the script · 0:56 – 1:08

**Audio:** *"This script creates a new branch, applies the code change, commits it, pushes to GitHub, and opens the pull request. There it is — the PR just opened."*

**On screen:** Terminal 2 still.

**Action:**
1. As the narrator says *"This script"* (right at 0:56) — press **Up arrow** to pull `./scripts/demo-trigger.sh` from history, then **Enter**.
2. Watch the script's output cascade: branch created → commit → push → PR opened.
3. As the narrator says *"There it is — the PR just opened"* (~1:05) — the script will have printed the PR URL. **Don't click it.** (We'll use the pre-loaded PR later.)

**Tip:** If you mis-type, just press Enter on whatever you typed and let the script auto-pick a new branch name on re-run. No need to panic.

---

### Beat 5 — Webhook lands, backend wakes up · 1:08 – 1:54

**Audio:** *"As soon as the push hits GitHub, a webhook fires. It lands on our backend, and you can see the job get enqueued. The worker picks it up immediately. First, it ensures the customer's repo is cached locally. Then it shells out to a bash script that does five things in about eight seconds: it creates an isolated git worktree at this PR's exact commit, runs npm ci to install dependencies, allocates a free port using atomic file locks, starts the app under PM2, and polls slash-api-slash-status until the app reports healthy."*

**On screen:** Switch to **Terminal 1 (backend log)**.

**Action:**
1. As the narrator says *"webhook fires"* (~1:10) — switch focus to Terminal 1. You'll see new log lines arriving live from the script you just ran.
2. The log will show: `enqueued pr_run (opened)` → `claimed job` → `cloning ...` (or `fetching ...`) → `preparing sandbox` → `creating worktree` → `npm ci` → `allocated port` → `ready: http://localhost:...`
3. Just let the log scroll naturally as the narrator describes each step. **No clicks.**

**Tip:** This 46-second beat is the longest. Don't rush. Let the viewer see real backend logs appear in real time.

---

### Beat 6 — Tests run · 1:54 – 2:10

**Audio:** *"Sandbox is up. Now the customer's test suite runs against the live sandbox. First Jest — unit tests plus HTTP integration tests that hit the running server. Then Playwright — real Chromium browser, real form fills, real clicks."*

**On screen:** Terminal 1 still.

**Action:** Just watch. The log shows `PASS tests/unit/users.test.js`, `PASS tests/integration/api.test.js`, then Playwright `✓ user can sign up...`, `✓ full user journey...`. No clicks.

---

### Beat 7 — Recording captured · 2:10 – 2:24

**Audio:** *"While Playwright runs the user journey, it captures a video. After tests pass, ffmpeg converts that video into a small GIF preview and a full MP4. Both get pushed to a dedicated artifacts branch."*

**On screen:** Terminal 1 still.

**Action:** Watch for the lines `recording: gif=...` and `uploading recording artifacts ...`. No clicks.

**Optional flourish:** If you have **Browser tab 3 (artifacts branch)** open, briefly tab-switch to it for 2 seconds at "*pushed to a dedicated artifacts branch*" to show the GIFs / MP4s landing there. Then return to terminal.

---

### Beat 8 — PR comment lands · 2:24 – 2:42

**Audio:** *"And here's the bot comment. Green check from the Check Run — that's the merge gate. Commit hash. Sandbox URL. An autoplaying GIF preview of the user journey, right inline. And a link to the full recording."*

**On screen:** Switch to **Browser tab 2 (★ pre-loaded PR)**.

**Action:**
1. Switch to the pre-loaded PR tab.
2. As the audio says each phrase, **hover** the cursor over that element:
   - *"green check from the Check Run"* → hover over the ✅ at the bottom of the PR
   - *"Commit hash"* → hover over the `Commit:` line
   - *"Sandbox URL"* → hover over the `Sandbox:` link
   - *"autoplaying GIF preview"* → hover over the GIF
   - *"link to the full recording"* → hover over the "▶ Watch the full ..." line

**Tip:** Don't actually click the GIF or links — just hover. Hovering serves the same visual purpose without navigating away.

---

### Beat 9 — Bridge to AI section · 2:42 – 2:46

**Audio:** *"But this is the part I really want to show you."*

**On screen:** Same PR tab.

**Action:** **Scroll down** to the second bot comment (the AI validation comment). End the scroll just as the audio finishes this line.

---

### Beat 10 — AI tests intro · 2:46 – 3:04

**Audio:** *"This is where Devzy goes beyond traditional CI. Claude looked at the diff — it saw the new endpoint and the new UI button — and generated tests that don't exist anywhere in the customer's repo. Devzy then ran those generated tests against the live sandbox."*

**On screen:** Second bot comment fully visible (headline + table).

**Action:** Don't click yet. Slowly **move the cursor** across the headline ("✅ Devzy: 3 AI-generated tests passed") as the audio says *"generated tests that don't exist anywhere"*. Slow movement = lets the viewer focus.

---

### Beat 11 — The breakdown · 3:04 – 3:12

**Audio:** *"In this case: two API-level Jest tests for the new endpoint, one Playwright test for the new button. All three passed."*

**On screen:** Same view.

**Action:** As each test is mentioned, **hover** over the corresponding row in the pass/fail table:
- *"two API-level Jest tests"* → hover the first two ✅ rows
- *"one Playwright test"* → hover the third ✅ row

---

### Beat 12 — Expand and walk through · 3:12 – 3:32

**Audio:** *"If you expand the details, you can see the actual test code Claude wrote — full files, ready to commit. Customers don't have to write these. Devzy does. Every push. Advisory by default, so a wrong AI test doesn't block merge, but a smart one catches the regression you forgot."*

**On screen:** Same view.

**Action:**
1. As the audio says *"expand the details"* — **click** the **▾ Details** collapsible.
2. Wait for the expanded view to render (~0.5s).
3. As the audio says *"actual test code Claude wrote"* — **click** the **▾ Test code** dropdown under the first test.
4. Scroll slightly to show the test code clearly in frame for ~5 seconds.
5. As the audio says *"advisory by default"* — scroll down a touch so the gray advisory note (*"This check is advisory and does not block merging"*) comes into view.

**Tip:** Don't rush the clicks. The audio gives you 20 seconds for this beat — use them.

---

### Beat 13 — Summary · 3:32 – 3:42

**Audio:** *"That's the full loop. One push. Sandbox. Full tests. AI-generated regression coverage. Screen recording. Under 90 seconds. Every PR."*

**On screen:** **Scroll back up** to the top of the PR so the green check ✅ and the first bot comment are visible together with the second.

**Action:** Slow scroll to top. Pause on the green Check Run + comments visible together as the audio finishes.

---

### Beat 14 — Wrap · 3:42 – 3:44

**Audio:** *"Thanks for watching."*

**On screen:** Hold the final shot (PR page with green check, both comments visible).

**Action:** Stop. Hit stop on your screen recorder ~1 second after the audio ends.

---

## If something goes wrong on tape

| Symptom | Quick recovery |
|---|---|
| Script run during beat 4 throws an error | Don't try to fix on camera. Stop recording, run `gh pr close <N>` on the broken PR, retry from the top |
| Backend log doesn't show `enqueued pr_run` after script runs | Smee tunnel died — but the pre-loaded PR is still there. Pivot: don't switch to backend terminal at beat 5, stay on browser narrating the steps |
| Audio drifts ahead of clicks | Pause the screen recording (most tools allow this), realign to audio, resume |
| Wrong tab in focus | Just tab-switch quickly. Viewer barely notices a half-second blip |

## After recording

1. **Trim** the head/tail dead time
2. If using Loom: hit "Remove silences" — it tidies awkward pauses
3. **Add the audio MP3** if you recorded silent (in iMovie: drag both files in, align, export)
4. Final length should be **~3:50** (audio 3:45 + ~5s trailing hold)

## Final pre-recording sanity script

Run this exactly once 2 minutes before hitting record:

```bash
cd /Users/omkar.chougale/Uncategorized/DevzySandboxTestingv2

# Confirm backend
curl -fsS http://localhost:3001/healthz | jq

# Confirm smee tunnel (look at terminal, should say "Connected")

# Pre-run the demo PR — wait ~90s for ALL comments to land before recording
./scripts/demo-trigger.sh
# → note the URL, open it in browser tab 2
# → wait for BOTH bot comments (test result + AI validation) before continuing
```

Once both comments are visible on the pre-run PR: you're ready. Hit record + play audio.

---

## File reference

- The trigger script (run live during beat 4): [`scripts/demo-trigger.sh`](scripts/demo-trigger.sh)
- The reference app being tested: [`stub-app/`](stub-app/)
- The README with architecture: [`README.md`](README.md)
