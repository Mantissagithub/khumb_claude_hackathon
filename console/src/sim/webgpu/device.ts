/** WebGPU device acquisition + capability check. */

export interface GpuContext {
  device: GPUDevice;
  adapterInfo: string;
}

/** Returns a GPU device, or null if WebGPU is unavailable (caller falls back to
 * the CPU path). Requests up to the adapter's storage-buffer limit so the engine
 * can bind its 8 storage buffers (the spec guarantees only 8 by default). */
export async function initWebGPU(): Promise<GpuContext | null> {
  if (!("gpu" in navigator) || !navigator.gpu) return null;
  let adapter: GPUAdapter | null = null;
  try {
    adapter = await navigator.gpu.requestAdapter({ powerPreference: "high-performance" });
  } catch {
    return null;
  }
  if (!adapter) return null;

  const want = adapter.limits.maxStorageBuffersPerShaderStage;
  const device = await adapter.requestDevice({
    requiredLimits: {
      maxStorageBuffersPerShaderStage: Math.min(want, 10),
    },
  });
  const info = (adapter as unknown as { info?: { description?: string } }).info?.description ?? "WebGPU";
  return { device, adapterInfo: info };
}
