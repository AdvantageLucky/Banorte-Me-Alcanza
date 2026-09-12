export function extractSurfaceId(messages) {
  const createMessage = (messages ?? []).find((message) => 'createSurface' in message);
  return createMessage?.createSurface?.surfaceId ?? null;
}
