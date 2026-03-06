# vibecod-sec-cheklist

Perform a security cheklist and write a markdown report. Format the output as a concise markdown technical report for security review. Save the findings to a Report.md file.

The report should include:
01 — SECRETS & CONFIG

Hardcoded secrets, tokens, or API keys in the codebase
Secrets leaking through logs, error messages, or API responses
Environment files committed to git
API keys exposed client-side that should be server-only
CORS too permissive
Dependencies with known vulnerabilities
Default credentials or example configs still present
Debug mode or dev tools enabled in production

02 — ACCESS & API

Pages or routes accessible without proper auth
Users accessing other users' data by changing an ID in the URL
Tokens stored insecurely on the client
Login or reset flows that reveal whether an account exists
Endpoints missing rate limiting
Error responses exposing internal details
Endpoints returning more data than needed
Sensitive actions (delete, change email) with no confirmation step
Admin routes protected only by hiding the URL

03 — USER INPUT

Unsanitized input reaching database queries
User-submitted text that can run code in other users' browsers
File uploads accepted without type or size checks
Payment or billing logic that can be bypassed client-side
