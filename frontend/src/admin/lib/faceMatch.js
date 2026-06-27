// ─────────────────────────────────────────────────────────────
// On-device face recognition (no server). Loads @vladmandic/face-api
// at runtime from a CDN (kept out of our bundle / Vite's optimizer),
// then: detect → 68-landmarks → 128-d descriptor, compared by
// euclidean distance. Descriptors are cached per photo URL.
// ─────────────────────────────────────────────────────────────

const FACEAPI_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.esm.js";
const MODEL_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model";

let _apiPromise = null;
function getApi() {
  if (!_apiPromise) {
    _apiPromise = import(/* @vite-ignore */ FACEAPI_URL).then((m) => m.default ?? m);
  }
  return _apiPromise;
}

let _modelsPromise = null;
export function loadModels() {
  if (!_modelsPromise) {
    _modelsPromise = getApi().then((faceapi) =>
      Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
      ])
    );
  }
  return _modelsPromise;
}

const _cache = new Map(); // url -> Float32Array | null

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

// 128-d descriptor for the (largest) face in the photo, or null.
export async function descriptorFor(url) {
  if (!url) return null;
  if (_cache.has(url)) return _cache.get(url);
  let desc = null;
  try {
    const faceapi = await getApi();
    await loadModels();
    const img = await loadImage(url);
    const det = await faceapi
      .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.35 }))
      .withFaceLandmarks()
      .withFaceDescriptor();
    desc = det?.descriptor ?? null;
  } catch {
    desc = null;
  }
  _cache.set(url, desc);
  return desc;
}

// Euclidean distance between two 128-d descriptors (pure, no lib needed).
export function distance(a, b) {
  if (!a || !b || a.length !== b.length) return null;
  let s = 0;
  for (let i = 0; i < a.length; i++) { const d = a[i] - b[i]; s += d * d; }
  return Math.sqrt(s);
}

// Map face distance → verdict. ~0.6 is the classic "same person" threshold.
export function faceVerdict(dist) {
  if (dist == null) {
    return {
      band: "NO_MATCH", label: "No usable face", is_match: false, confidence_pct: 0, score: 0,
      reasons: ["No clear face detected in one of the photos — can't compare faces.",
        "On-device face recognition · decision support only."],
      source: "face", noFace: true,
    };
  }
  const sim = Math.max(0, 1 - dist / 0.6); // 0..1
  const pct = Math.round(sim * 1000) / 10;
  let band, label;
  if (dist <= 0.40) { band = "STRONG"; label = "Match — very likely the same person"; }
  else if (dist <= 0.50) { band = "LIKELY"; label = "Likely the same person"; }
  else if (dist <= 0.62) { band = "POSSIBLE"; label = "Possible — needs human review"; }
  else { band = "NO_MATCH"; label = "No match found"; }
  return {
    band, label, is_match: band === "STRONG" || band === "LIKELY",
    confidence_pct: pct, score: Math.round((1 - dist) * 1e4) / 1e4,
    reasons: [
      `Face similarity ${sim.toFixed(2)} (distance ${dist.toFixed(2)}) — ${band.toLowerCase().replace("_", " ")}.`,
      "On-device face recognition (FaceNet-style 128-d descriptors).",
      "Decision support only — a trained operator must visually confirm before any reunification.",
    ],
    source: "face",
  };
}
