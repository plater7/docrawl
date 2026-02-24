# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in Docrawl, please report it responsibly.

### Private Disclosure (Preferred)

1. **Do NOT open a public issue** for security vulnerabilities
2. Email the maintainer or use GitHub's private vulnerability reporting feature
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Affected files and lines
   - Suggested fix (if any)
   - Severity assessment (Critical/High/Medium/Low)

### What to Expect

- Acknowledgment within 48 hours
- Status update within 7 days
- Fix timeline depends on severity:
  - **Critical**: Patch within 72 hours
  - **High**: Patch within 2 weeks
  - **Medium/Low**: Next scheduled release

## Known Security Considerations

Docrawl is a documentation crawling tool that:
- Makes HTTP requests to external URLs via Playwright
- Sends content to Ollama LLM APIs for processing
- Writes files to the local filesystem

These operations require careful handling of:
- **Path traversal**: Output paths must be validated
- **SSRF**: URL validation before crawling
- **Input sanitization**: User-provided URLs and configurations
- **Container security**: Least-privilege Docker configuration

## Security Best Practices for Deployment

- Run behind a reverse proxy with rate limiting
- Use the Cloudflare Worker + Tunnel setup for public exposure
- Keep dependencies updated (Dependabot is configured)
- Never expose the Ollama API directly to the internet
- Review output paths before starting crawl jobs
