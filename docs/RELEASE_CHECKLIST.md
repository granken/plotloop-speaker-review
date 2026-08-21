# 发布前检查清单

## 版本边界

- 远程基线与本地分支已经同步，明确本次版本号和目标标签。
- `package.json`、`CHANGELOG.md` 和静态资源查询参数使用同一版本号。
- 只提交产品源码、脱敏示例、测试和公开文档。

## 隐私与仓库卫生

- `local-review-data.js`、`local-review-config.js`、`.local/` 和 `*.backup-*` 保持忽略。
- 不包含真实花名册、会议标题、逐字稿、总结、群 ID、open_id、密钥或本机绝对路径。
- `automation/config.example.json` 只保留通用路径与占位标识。
- 本地回写目录来自环境变量或仓库外配置，不在源码中写死。

## 自动验证

```bash
git fetch --prune origin
npm run test:release
python3 -m compileall -q automation scripts
git diff --check
git status --short --ignored
```

## 手工验收

- GitHub Pages：可以导入、确认、复制和下载；不显示“确认并回写”。
- `?demo=1`：不读取或覆盖本地会议与联系人数据，也不显示回写入口。
- 本地服务：显示“确认并回写”，有效批次落入配置的确认目录。
- 桌面与窄屏：确认按钮、姓名选择、会议队列和结果抽屉无重叠。
- 自动化影子模式：不发飞书、不写目标目录、不修改源录音。
- 飞书卡片：高疑惑优先、最多四场一张、编号跨卡连续，失败可退回纯文字。

## 提交边界

- 先审阅 `git diff --stat` 和 `git diff`。
- 只用明确路径暂存，不使用全量暂存命令。
- 提交后再次运行 `npm run test:release`，再创建标签和推送。
