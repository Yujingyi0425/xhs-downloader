# XHS Travel Collector：TC0R Toolchain Preflight

## 阶段

```text
PHASE=TC0R
BASELINE_COMMIT=2d3d2fc9cb341c0ce04f5d5d6b6dc81ab2e60236
```

## 架构修复

```text
ARCH_DEPENDENCY_DIRECTION=PASS
```

`ARCHITECTURE.md` 已明确区分 compile/import dependency direction 与 runtime call/dependency injection direction，并明确 `xhs-core` 不得 import `xhs-adapters`。

## Extension 工具链

版本来自本机实际命令：

```text
NODE_VERSION=v24.19.0
PNPM_VERSION=11.19.0
```

仓库 `apps/extension/package.json` 实际 scripts 为 `check`、`lint`、`test`、`build`；未凭空增加命令。

首次失败根因是命令环境未将 bundled Node 目录加入 PATH，导致依赖安装的 esbuild postinstall 找不到 `node`。补充本机 bundled Node 到 PATH 后，未修改仓库配置，以下安装成功：

```text
INSTALL_RESULT=PASS（pnpm install --frozen-lockfile）
```

顺序执行 Extension 验证：

```text
EXTENSION_CHECK=PASS（tsc --noEmit）
EXTENSION_LINT=PASS（eslint .）
EXTENSION_TEST=PASS（55 files / 282 tests；coverage branches 87.42%）
EXTENSION_BUILD=PASS（node build.mjs）
```

## Python

```text
UV_STATUS=UNAVAILABLE
PYTHON_TOOLCHAIN_REQUIRED_BEFORE=TC2
```

TC1 不依赖 Python，因此不阻塞 TC0R → TC1；TC2 前必须补齐 Python/uv 工具链。

## 变更与安全检查

本阶段只修改 `docs/travel-collector/*.md`，未修改 `package.json`、lockfile 或运行时代码。依赖安装产生的 `node_modules`、扩展构建产物和 coverage 目录未进入 Git；未发现真实用户数据、Cookie、`xsec_token` 或其他本机敏感文件进入提交。
