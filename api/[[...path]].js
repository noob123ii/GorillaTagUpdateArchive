/**
 * Vercel serverless function: proxies /api/* to the Base44 backend.
 * Runs on your Vercel deployment so API calls use your base URL (e.g. yourapp.vercel.app/api/...).
 * Set BASE44_APP_BASE_URL in Vercel env (e.g. https://gorilla-patch-hub.base44.app)
 */
export default async function handler(req, res) {
  const baseUrl = process.env.BASE44_APP_BASE_URL || process.env.VITE_BASE44_APP_BASE_URL;
  if (!baseUrl) {
    return res.status(500).json({ error: 'BASE44_APP_BASE_URL not configured' });
  }

  const path = req.query.path;
  const backendPath = Array.isArray(path) ? path.join('/') : (path || '');
  const target = `${baseUrl.replace(/\/$/, '')}/${backendPath}`;
  const url = req.url?.includes('?') ? `${target}${req.url.slice(req.url.indexOf('?'))}` : target;

  try {
    const headers = {};
    for (const [k, v] of Object.entries(req.headers)) {
      if (k.toLowerCase() !== 'host' && k.toLowerCase() !== 'content-length' && v) {
        headers[k] = Array.isArray(v) ? v[0] : v;
      }
    }

    const opts = { method: req.method, headers };
    if (!['GET', 'HEAD'].includes(req.method) && req.body) {
      opts.body = req.body;
    }

    const proxyRes = await fetch(url, opts);
    const data = await proxyRes.arrayBuffer();
    res.status(proxyRes.status);
    proxyRes.headers.forEach((v, k) => res.setHeader(k, v));
    res.end(Buffer.from(data));
  } catch (err) {
    console.error('API proxy error:', err);
    res.status(502).json({ error: 'Backend unavailable' });
  }
}
