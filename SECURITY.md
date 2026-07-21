# Security

## Supported version

Security fixes currently target the latest \`main\` branch.

## Reporting

Please avoid opening a public issue if a report contains real meeting data, names, credentials or local file paths. Contact the repository maintainer privately and include only the minimum reproduction data.

## Browser model

The application is a static local tool. It does not execute imported content as HTML and renders user-provided strings with DOM text fields. Imported JSON should still be treated as untrusted data and reviewed before downstream automation writes changes into source documents.
