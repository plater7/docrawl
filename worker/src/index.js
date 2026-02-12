export default {
  async fetch(request, env) {
    // Construir la URL destino usando el VPC Service binding
    // env.VPC_SERVICE es un Fetcher que rutea a través del tunnel
    const url = new URL(request.url);
    const targetUrl = new URL(url.pathname + url.search, "http://vpc-service");

    // Proxy de requests HTTP a través del VPC Service binding
    const response = await env.VPC_SERVICE.fetch(targetUrl.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });

    return response;
  },
};
