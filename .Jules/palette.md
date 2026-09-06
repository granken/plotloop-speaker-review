## 2023-10-27 - Loading Spinner UX Enhancement
**Learning:** Adding a loading text state to buttons triggering asynchronous fetch requests is a safe and effective micro-UX enhancement. It prevents redundant submissions and clearly communicates background processing to users. Restoring `innerHTML` instead of `textContent` is important to preserve inner elements or structure if they exist.
**Action:** Always save `innerHTML` (or inner structure) before swapping a button state to a loading indicator, and restore it via `finally` blocks when the promise settles.
