import { createParser, type EventSourceMessage } from "eventsource-parser";

const MAX_PENDING_EVENT_BYTES = 1024 * 1024;

export type ParsedSseEvent = {
  event: string;
  data: unknown;
};

export async function consumeSseResponse(
  response: Response,
  onEvent: (event: ParsedSseEvent) => boolean | void
) {
  if (!response.body) {
    throw new Error("当前浏览器不支持流式回答。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let pendingBytes = 0;
  let stopped = false;
  const parser = createParser({
    onEvent(message: EventSourceMessage) {
      if (stopped) return;
      pendingBytes = 0;
      let data: unknown;
      try {
        data = JSON.parse(message.data);
      } catch {
        return;
      }
      stopped = onEvent({ event: message.event || "message", data }) === false;
    }
  });

  try {
    while (!stopped) {
      const { done, value } = await reader.read();
      if (done) break;
      pendingBytes += value.byteLength;
      if (pendingBytes > MAX_PENDING_EVENT_BYTES) {
        throw new Error("流式事件超过安全大小限制。");
      }
      parser.feed(decoder.decode(value, { stream: true }));
    }
    const tail = decoder.decode();
    if (tail) parser.feed(tail);
    parser.reset({ consume: true });
  } finally {
    if (stopped) await reader.cancel();
    reader.releaseLock();
  }
}
