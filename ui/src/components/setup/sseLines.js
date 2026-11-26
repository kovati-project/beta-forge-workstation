/**
 * Read an SSE response body and call onMessage for each "data: " line.
 * Buffers across chunks, so a line split between two reads is not lost.
 */
export async function readSSE(response, onMessage) {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split('\n');
    buffer = done ? '' : lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) onMessage(line.slice(6));
    }
    if (done) break;
  }
}
