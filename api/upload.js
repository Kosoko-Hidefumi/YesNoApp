import { put } from "@vercel/blob";
import { randomUUID } from "crypto";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const ALLOWED = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);
const EXT = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/gif": ".gif",
  "image/webp": ".webp",
};

function json(data, status = 200) {
  return Response.json(data, { status, headers: cors });
}

function detectMime(file) {
  if (ALLOWED.has(file.type)) return file.type;
  const name = (file.name || "").toLowerCase();
  if (/\.jpe?g$/.test(name)) return "image/jpeg";
  if (/\.png$/.test(name)) return "image/png";
  if (/\.gif$/.test(name)) return "image/gif";
  if (/\.webp$/.test(name)) return "image/webp";
  return "";
}

export default {
  async OPTIONS() {
    return new Response(null, { status: 204, headers: cors });
  },

  async POST(request) {
    try {
      const formData = await request.formData();
      const file = formData.get("file");
      if (!file || typeof file === "string") {
        return json({ error: "file フィールドが必要です" }, 400);
      }
      const mime = detectMime(file);
      if (!ALLOWED.has(mime)) {
        return json({ error: "画像ファイル（JPEG/PNG/GIF/WebP）を選んでください" }, 400);
      }
      const blob = await put(`uploads/${randomUUID()}${EXT[mime]}`, file, {
        access: "public",
        contentType: mime,
      });
      return json({ url: blob.url });
    } catch (error) {
      console.error("Upload error:", error);
      const msg = error instanceof Error ? error.message : "アップロードに失敗しました";
      if (/private|access/i.test(msg)) {
        return json({
          error: "BlobストアがPrivateです。StorageでPublicストアを作成して接続し直してください。",
        }, 500);
      }
      return json({ error: msg }, 500);
    }
  },
};
