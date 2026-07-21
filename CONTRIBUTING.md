# Contributing

Thanks for improving PlotLoop Speaker Review.

## Before a change

- Keep the default experience local-first and dependency-light.
- Do not add real meeting records or roster data.
- Preserve the \`speaker-review v2\` output contract unless the change includes a migration path.
- Make low-confidence and human-confirmed states visibly different.
- Keep \`index.html\` usable when opened directly from disk.

## Local checks

\`\`\`bash
npm test
git diff --check
\`\`\`

For interface changes, verify at least one desktop viewport and one phone viewport. Check that meeting titles, names, notes and action buttons do not overlap.
