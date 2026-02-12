export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const tunnelUrl = `https://${env.TUNNEL_HOSTNAME}${url.pathname}${url.search}`;

    const modifiedRequest = new Request(tunnelUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });

    return fetch(modifiedRequest);
  },
};
