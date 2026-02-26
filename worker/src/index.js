// Docrawl Cloudflare Worker
//
// Authentication is handled by Cloudflare Zero Trust (Access) at the network
// layer via OTP email. This worker only sanitizes headers before forwarding
// to prevent header injection — closes CONS-004 / issue #50.

const ALLOWED_HEADERS = ['content-type', 'accept', 'x-api-key'];

export default {
  async fetch(request, env) {
    // Sanitize headers — only forward explicitly allowed headers
    const safeHeaders = new Headers();
    for (const [key, value] of request.headers) {
      if (ALLOWED_HEADERS.includes(key.toLowerCase())) {
        safeHeaders.set(key, value);
      }
    }

    const url = new URL(request.url);
    return env.VPC_SERVICE.fetch(url.pathname + url.search, {
      method: request.method,
      headers: safeHeaders,
      body: request.body,
    });
  },
};
