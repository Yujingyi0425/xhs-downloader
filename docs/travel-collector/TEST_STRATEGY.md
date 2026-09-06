# XHS Travel Collector：TC0 测试策略

## TC0 基线验证

TC0 不新增运行时代码，因此不伪造功能测试 PASS。应记录当前基线命令结果：

```text
uv run ruff check .
uv run ruff format --check .
uv run pytest
pnpm format:check
pnpm lint
pnpm check
pnpm test
pnpm build
pnpm verify
```

后续实现必须区分原有失败与任务相关失败，并保留证据。

## TC1 合成 DOM 契约

使用完全合成 DOM，覆盖 10、49、500 条；虚拟列表回收导致可见数量变化 `10 → 18 → 13 → 22`；重复 feed、相同 feed 不同位置、混合图文/视频、缺标题/作者/token、非笔记链接、正常到底、滚动卡死、最大轮数和 token 刷新。核心不变量是累计 Map 只增不减，最终唯一 feed 数等于期望数。

## TC2 持久化

覆盖空/单条/49/500 条、重复导入、快照差异、重启恢复、事务回滚、非法条目、token 不出 repr/日志/API/导出，以及数据库并发写入。

## TC3 详情编排

覆盖图文/视频成功、token 过期、删除/不可用、扩展离线、任务超时、重启、重复入队、坏结果、有限并发、失败到 `NEEDS_REIMPORT`，并验证没有新建 HTTP/HTML 抓取路径。

## TC4 媒体与下载

覆盖单图、多图、视频、媒体缺失、CDN 失败、部分失败、重试、过期缓存、重复下载、重启、URL 指纹变化、SHA-256 和原子替换。只有所有必需媒体完成才允许 ready。

## TC5 视频预处理

使用合成或明确授权的 10 秒/60 秒视频，覆盖无声、中文、日文、中日混合、FFmpeg 缺失、STT 缺失、中断恢复和关键帧上限。验证 transcript 时间段结构、TXT 同步和 `NOT_CONFIGURED`。

## TC6–TC8

验证稳定排序、敏感字段清洗、坏路径、空数据、partial、长文本、500 条、窄屏无横向溢出；最后验证 `EXPORT_NOTE_COUNT == UNIQUE_ITEMS`，并明确列出详情/媒体/转录失败。

## 安全测试原则

所有 fixture 使用 synthetic 值；测试断言 token、Cookie、signed URL query、能力令牌和正文不会进入日志、公开响应或导出。不得通过删除断言、放宽覆盖率或 mock 真实失败来取得 PASS。
