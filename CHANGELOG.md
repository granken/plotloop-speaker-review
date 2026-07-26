# Changelog

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
