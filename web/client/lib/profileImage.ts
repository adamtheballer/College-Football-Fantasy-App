const MAX_SOURCE_FILE_BYTES = 10 * 1024 * 1024;
const MAX_PROFILE_IMAGE_BYTES = 250 * 1024;
const OUTPUT_EDGE_PX = 256;
// iOS commonly supplies library photos as HEIC/HEIF. The browser decodes the
// source and we always persist the canvas output as JPEG, so these are safe to
// accept alongside the formats browsers traditionally expose.
const ALLOWED_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif",
]);
const SUPPORTED_IMAGE_MESSAGE = "Choose an image from your photo library. JPEG, PNG, WebP, and iPhone photos are supported.";

const base64ByteLength = (dataUrl: string) => {
  const encoded = dataUrl.slice(dataUrl.indexOf(",") + 1);
  const padding = encoded.endsWith("==") ? 2 : encoded.endsWith("=") ? 1 : 0;
  return Math.floor((encoded.length * 3) / 4) - padding;
};

const loadImage = (source: string) => new Promise<HTMLImageElement>((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image);
  image.onerror = () => reject(new Error(`This photo could not be read. ${SUPPORTED_IMAGE_MESSAGE}`));
  image.src = source;
});

/**
 * Produces a small JPEG data URL suitable for an avatar. Keeping the image
 * compact lets the existing self-profile PATCH persist it without depending
 * on a third-party image host or an ephemeral application filesystem.
 */
export async function prepareProfileImage(file: File): Promise<string> {
  // Some mobile browsers omit the MIME type for a photo-library selection.
  // Let the browser decoder make the final determination for that case.
  if (file.type && !ALLOWED_IMAGE_TYPES.has(file.type)) {
    throw new Error(SUPPORTED_IMAGE_MESSAGE);
  }
  if (file.size > MAX_SOURCE_FILE_BYTES) {
    throw new Error("Choose a photo smaller than 10 MB.");
  }

  const source = URL.createObjectURL(file);
  try {
    const image = await loadImage(source);
    const largestSide = Math.max(image.naturalWidth, image.naturalHeight);
    if (!largestSide) {
      throw new Error(`This photo could not be read. ${SUPPORTED_IMAGE_MESSAGE}`);
    }
    const scale = Math.min(1, OUTPUT_EDGE_PX / largestSide);
    const width = Math.max(1, Math.round(image.naturalWidth * scale));
    const height = Math.max(1, Math.round(image.naturalHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Your browser could not prepare this photo. Try a different photo.");
    }
    context.drawImage(image, 0, 0, width, height);

    // JPEG is universally rendered by the app and keeps a 256px avatar very
    // small. Lower quality once if a detailed photo still exceeds the API cap.
    let output = canvas.toDataURL("image/jpeg", 0.82);
    if (base64ByteLength(output) > MAX_PROFILE_IMAGE_BYTES) {
      output = canvas.toDataURL("image/jpeg", 0.62);
    }
    if (base64ByteLength(output) > MAX_PROFILE_IMAGE_BYTES) {
      throw new Error("This photo is too detailed to use. Try a different photo.");
    }
    return output;
  } finally {
    URL.revokeObjectURL(source);
  }
}
