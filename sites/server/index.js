/**
 * Minimal Cloudflare Worker entry for the static learning workspace.
 * Sites provides the ASSETS binding for files emitted into dist/.
 */
export default {
  async fetch(request, env) {
    if (!env?.ASSETS?.fetch) {
      return new Response("Static asset binding is unavailable", { status: 503 });
    }

    const response = await env.ASSETS.fetch(request);
    if (response.status !== 404 || request.method !== "GET") return response;

    const url = new URL(request.url);
    url.pathname = "/index.html";
    return env.ASSETS.fetch(new Request(url, request));
  },
};
