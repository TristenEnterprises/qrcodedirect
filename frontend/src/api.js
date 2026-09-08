// QRCodeDirect API client (session cookie auth)
async function j(url, opts = {}) {
  const headers = { ...(opts.body ? { "Content-Type": "application/json" } : {}), ...(opts.headers || {}) };
  const r = await fetch(url, { credentials: "include", ...opts, headers });
  if (r.status === 401 && !url.startsWith("/api/auth/")) {
    window.location.href = "/login";
    throw new Error("Session expired");
  }
  const ct = r.headers.get("content-type") || "";
  const d = ct.includes("json") ? await r.json().catch(() => ({})) : await r.text();
  if (!r.ok) throw new Error((d && d.detail) || d || `Error ${r.status}`);
  return d;
}

export const api = {
  me: () => j("/api/auth/me"),
  login: (b) => j("/api/auth/login", { method: "POST", body: JSON.stringify(b) }),
  register: (b) => j("/api/auth/register", { method: "POST", body: JSON.stringify(b) }),
  logout: () => j("/api/auth/logout", { method: "POST" }),
  links: () => j("/api/v1/links"),
  link: (slug) => j(`/api/v1/links/${slug}`),
  create: (b) => j("/api/v1/links", { method: "POST", body: JSON.stringify(b) }),
  update: (slug, b) => j(`/api/v1/links/${slug}`, { method: "PATCH", body: JSON.stringify(b) }),
  del: (slug) => j(`/api/v1/links/${slug}`, { method: "DELETE" }),
  stats: (slug, days) => j(`/api/v1/links/${slug}/stats?days=${days}`),
  preview: async (b) => {
    const r = await fetch("/api/v1/preview", {
      credentials: "include",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(b),
    });
    if (!r.ok) throw new Error("Preview failed");
    const bytes = new Uint8Array(await r.arrayBuffer());
    const CH = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let out = "";
    for (let i = 0; i < bytes.length; i += 3) {
      const b0 = bytes[i], b1 = bytes[i + 1], b2 = bytes[i + 2];
      out += CH[b0 >> 2] + CH[((b0 & 3) << 4) | (b1 === undefined ? 0 : b1 >> 4)];
      if (b1 === undefined) out += "==";
      else {
        out += CH[((b1 & 15) << 2) | (b2 === undefined ? 0 : b2 >> 6)];
        out += b2 === undefined ? "=" : CH[b2 & 63];
      }
    }
    return "data:image/png;base64," + out;
  },
};

export function hexLum(hex) {
  const h = String(hex || "#000000").replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.padEnd(6, "0");
  const n = parseInt(full.slice(0, 6), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}

export function styleWarnings(style) {
  const out = [];
  const hasLogo = style.logo && style.logo.data;
  const mode = style.fg_mode || "solid";
  let lightest = hexLum(style.fg);
  if (mode === "gradient" && Array.isArray(style.fg_gradient)) {
    lightest = Math.max(...style.fg_gradient.map(hexLum));
  }
  if (hasLogo && lightest > 0.32) {
    out.push("With a centre logo the code colour needs to stay dark so it scans reliably.");
  }
  if (hasLogo && style.logo.scale > 26) out.push("Keep the logo at 26% or smaller or the code may not scan.");
  return out;
}

export const DEFAULT_STYLE = {
  fg_mode: "solid",
  fg: "#0B0B09",
  fg_gradient: ["#0B0B09", "#E85D3F"],
  fg_angle: 45,
  bg: "#FAF7F0",
  dots: "rounded",
  logo: null,
  margin: 3,
  scale: 12,
  ec: "H",
};
