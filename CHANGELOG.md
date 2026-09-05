# Changelog

## Unreleased

## 0.5.0 - 2026-09-05

- Added deterministic, zero-model processing for confirmed `speaker-review v2` JSON, including strict validation, speaker writeback, timestamp preservation, index and ledger updates, completion signals and processed-file archival.
- Added a private learned-roster store and local `/api/roster` endpoint so human-confirmed names remain available in later review sessions without entering the public repository.
- Made local “确认并回写” report the completed writeback result instead of only queueing the JSON when automation is configured.
- Fixed nanosecond UTC timestamps falling back to unconverted text and removed obsolete pending-review notes during confirmed writeback.
- Added time-segment speaker replacement for transcripts whose ASR output reuses one label for multiple people.
- Updated the public workbench preview to match the 0.5.0 review experience.

## 0.4.0 - 2026-08-22

- Added an optional local-first YoooClaw recording discovery and staging workflow.
- Added protected hotword correction, Codex `speaker-review v2` analysis and work/private routing.
- Added compact Lark reply parsing, confirmation-gated writeback and completion signals.
- Replaced plain-text Lark review dispatch with structured Card 2.0 messages that prioritize uncertain meetings, collapse evidence and split large batches for mobile readability.
- Kept the compact text reply protocol and added automatic plain-text fallback when card delivery fails.
- Added an optional one-click local submit action that posts confirmed JSON to `/api/confirm`; hosted and forced-demo pages keep the action hidden.
- Added timestamp-preserving archival, index de-duplication, launchd templates and shadow-mode safety defaults.
- Normalized UTC recording timestamps to the machine's local timezone before review and index rendering.
- Added a public-repository check for local data, backup files, absolute home paths and non-placeholder Lark identifiers.
- Added GitHub Actions coverage for the same web, automation and public-repository release gate used locally.
- Kept local paths, rosters, identities, chat IDs, transcripts and runtime state outside Git.

## 0.3.3 - 2026-07-27

- Made `?demo=1` a fully isolated demo mode that ignores local meeting and roster storage.
- Prevented demo interactions from overwriting or clearing the user's personal browser state.

## 0.3.2 - 2026-07-25

- Moved the continuous review controls from the bottom-right area to a compact bar beside the one-line summary.
- Put “确认并下一场” before “跳过” so the primary review path is always the first action.
- Kept the command bar compact on narrow mobile viewports and moved summary and meeting popovers below it.

## 0.3.1 - 2026-07-23

- Added click-outside dismissal to the automatic one-line summary preview.
- Kept the copy and result controls pinned to the right edge as the window narrows.

## 0.3.0 - 2026-07-23

- Reworked the desktop layout around a wide review area; JSON output is now a closed-by-default drawer.
- Added a touch-friendly speaker picker with recent names, the full local roster and a manual fallback.
- Compressed each speaker mapping to one line and moved evidence editing and mobile deletion behind an on-demand control.
- Moved meeting metadata into the title and added a five-second summary preview when switching meetings.
- Removed summary excerpts from the queue and eliminated horizontal scrolling in the 390 px review layout.

## 0.2.0 - 2026-07-22

- Added private local task and roster injection files that remain excluded from Git.
- Moved roster management into a low-frequency dialog and kept the review action bar fixed near speaker decisions.

## 0.1.0 - 2026-07-21

- Extracted the private speaker-review workflow into a standalone, sanitized project.
- Added JSON import, queue filters, local roster, batch confirmation and JSON export.
- Added automatic \`replace\` and \`high\` updates after a human changes the suggested speaker.
- Added responsive desktop and mobile review views.
- Added fictional examples, privacy guidance and core logic tests.
