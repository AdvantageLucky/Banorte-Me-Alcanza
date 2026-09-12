export function dropDuplicateCreateSurface(messages, existingSurfaceIds) {
  return (messages ?? []).filter((message) => {
    if (!('createSurface' in message)) {
      return true;
    }
    return !existingSurfaceIds.has(message.createSurface.surfaceId);
  });
}
