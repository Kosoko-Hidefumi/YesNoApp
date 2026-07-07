import { put, head } from "@vercel/blob";
import { randomUUID } from "crypto";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function json(data, status = 200) {
  return Response.json(data, { status, headers: cors });
}

function blobAuth() {
  const rw = process.env.BLOB_READ_WRITE_TOKEN;
  const storeId = process.env.BLOB_STORE_ID;
  const oidc = process.env.VERCEL_OIDC_TOKEN;
  if (rw) return { token: rw };
  if (storeId && oidc) return { storeId, oidcToken: oidc };
  return null;
}

function isValidConfig(cfg) {
  return cfg && cfg.q && Array.isArray(cfg.n) && Array.isArray(cfg.c);
}

export default {
  async OPTIONS() {
    return new Response(null, { status: 204, headers: cors });
  },

  async GET(request) {
    const id = new URL(request.url).searchParams.get("id");
    if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
      return json({ error: "リンクIDが不正です" }, 400);
    }
    const auth = blobAuth();
    if (!auth) return json({ error: "Blobの認証設定がありません" }, 500);
    try {
      let blobUrl;
      try {
        const meta = await head(`shares/${id}.json`, auth);
        blobUrl = meta.url;
      } catch (headErr) {
        const msg = headErr instanceof Error ? headErr.message : "";
        if (/not found/i.test(msg) || headErr?.name === "BlobNotFoundError") {
          return json({ error: "リンクが見つかりません" }, 404);
        }
        throw headErr;
      }
      const res = await fetch(blobUrl);
      if (!res.ok) return json({ error: "設定の読み込みに失敗しました" }, 500);
      const cfg = await res.json();
      if (!isValidConfig(cfg)) return json({ error: "設定が不正です" }, 500);
      return json(cfg);
    } catch (error) {
      console.error("Share GET error:", error);
      const msg = error instanceof Error ? error.message : "";
      if (/not found/i.test(msg) || error?.name === "BlobNotFoundError") {
        return json({ error: "リンクが見つかりません" }, 404);
      }
      return json({ error: "設定の読み込みに失敗しました" }, 500);
    }
  },

  async POST(request) {
    const auth = blobAuth();
    if (!auth) return json({ error: "Blobの認証設定がありません" }, 500);
    try {
      const cfg = await request.json();
      if (!isValidConfig(cfg)) return json({ error: "設定が不正です" }, 400);
      const id = randomUUID();
      const pathname = `shares/${id}.json`;
      await put(pathname, JSON.stringify(cfg), {
        ...auth,
        access: "public",
        contentType: "application/json",
        addRandomSuffix: false,
      });
      return json({ id });
    } catch (error) {
      console.error("Share POST error:", error);
      return json({ error: "リンク作成に失敗しました" }, 500);
    }
  },
};
