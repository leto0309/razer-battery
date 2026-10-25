# razer-battery

本项目由 AI Dev Factory 创建。需求与架构记录在 docs/。
PowerShell 7：`./scripts/verify.ps1` 运行真实测试，`./scripts/build.ps1` 构建，
`./scripts/package.ps1` 先验证再生成 dist/ 产物。
质量门槛随项目一起保存：C/C++ 编译警告即错误，.NET 警告即错误，Python 测试中的警告视为失败，
Python 还会用 pyproject.toml 中固定规则的 ruff 检查未使用的导入、未定义的名称和语法问题，Node 的 verify 会对 src/ 和 scripts/ 下所有 .js/.mjs/.cjs 做语法检查。
Python 外部独立使用先执行 `python -m pip install -r requirements-dev.txt`。
Node 模板依赖标准库，`npm start` 启动本地网页（默认只绑定 127.0.0.1）。
CI 自动验证 PR，Release 需要 main 上已合并代码、maintainer 手动触发和 release 环境审批。
发布操作不会自动合并代码。
