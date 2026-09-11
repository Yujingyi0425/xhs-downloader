/** 返回消息对应的顶层标签页 URL；content script 的 sender.url 可能为空。 */
export function pageUrlFromSender(sender: {
  url?: string;
  tab?: { url?: string };
}): string | undefined {
  return sender.tab?.url ?? sender.url;
}
