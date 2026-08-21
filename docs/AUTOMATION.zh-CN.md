# 录音自动化与飞书确认

这套自动化把 YoooClaw 已落库的录音材料复制到独立暂存区，执行热词校正和说话人初判，再通过飞书极简回复完成确认。确认前不写目标目录，任何阶段都不修改 YoooClaw 原始文件。

## 主流程

1. 每 5 分钟由 macOS 唤醒一次，程序内部按工作日/周末和时间段判断本次是否需要扫描。
2. 同时检查 YoooClaw 清单和 `audio/*.ogg`，以 UUID 去重；转写或总结缺失 30 分钟后产生告警。
3. 转写、总结和音频连续两次文件指纹一致后，复制到本地状态目录。
4. 在暂存副本上做热词校正，并让 Codex 输出 `speaker-review v2` 与工作/私人分类。
5. 工作材料使用飞书 Card 2.0 发到指定工作群；私人内容默认不发群，只生成本地确认批次。
6. 回复“全对”“2=姓名”“3留”“4忽略”。只有全部编号明确后，程序才写回目标目录、更新索引和完成信号。

## 飞书确认卡片

第一版卡片只改善阅读，不改变确认协议：

- 疑惑项较多的会议优先排列，第一场默认展开。
- 每场会议独立折叠，展开后显示日期时间、一句话总结、编号映射、置信度、处理方式和判断依据。
- 每张卡片最多承载 4 场会议；更大的批次自动拆成多张卡，编号仍在整个批次内连续。
- 用户继续使用“全对”“2=姓名”“3留”“4忽略”等文字回复，不依赖按钮回调服务。
- 卡片 JSON 会保存在批次状态目录中，便于审计与问题复现。
- 卡片发送失败时自动发送原有纯文字版本，确认链路不会中断。

该版本不监听 `card.action.trigger`，也不会因为展开或收起会议触发任何文档写回。

## 安全默认值

- `enabled=false`：新安装不会自行运行。
- `mode=shadow`：只生成本地批次，不发飞书、不写目标文档。
- `lark.dry_run=true`：即使误开飞书，也不会真实发送。
- `allow_private_content=false`：私人内容不会进入工作群。
- 源目录只读；热词校正、模型输出、确认状态都保存在仓库外。

## 本地配置

复制 `automation/config.example.json` 到：

```text
~/.config/plotloop-speaker-review/config.json
```

配置内可包含本机目录、飞书群 ID 和本人 open_id。该文件不在 Git 仓库内，不应提交。

`timezone` 决定录音时间在工作台、同名文件后缀和索引中的显示方式，默认是 `Asia/Shanghai`。显式配置后，自动化在本机和 CI 等不同时区的机器上会保持一致。

## 工作台一键提交

使用 `npm run serve` 启动本地页面后，工作台会显示“确认并回写”。它把已确认的 `speaker-review v2` JSON 提交到同源的 `/api/confirm`，不会直接修改转写文件。

待处理目录按以下优先级解析：

1. 环境变量 `PLOTLOOP_CONFIRMED_DIR`。
2. `PLOTLOOP_CONFIG` 指向配置文件中的 `confirmed_dir`。
3. 配置文件中的 `work_target/confirmed`。
4. 项目内已忽略的 `.local/confirmed`。

GitHub Pages、其他远程站点和 `?demo=1` 强制示例模式不会显示本地提交按钮。服务默认只监听 `127.0.0.1:4173`，也不会开放跨站写入。

## 常用命令

```bash
python3 -m automation preflight
python3 -m automation baseline --yes
python3 -m automation run --force
python3 -m automation status
python3 -m automation classify --recording RECORDING_UUID --as work
python3 -m automation apply-reply --batch SR-20260804-120000 --text "全对"
```

当模型无法可靠区分工作与私人材料时，该录音不会发到飞书，也不会生成可写回批次。先用 `classify` 明确目录，下次扫描才继续流转。

第一次正式启用前先执行 `baseline --yes`，把此前已经人工处理过的录音记为历史边界。否则它们会被当作新录音。

## 定时运行

`scripts/manage_launchd.py render` 只生成 LaunchAgent 文件，不启用；确认影子运行无误后，再使用 `install`。launchd 每 5 分钟唤醒一次，真正扫描频率由配置决定：

- 工作日 09:30-22:00：5 分钟。
- 工作日其他时段：30 分钟。
- 周末 09:30-22:00：30 分钟。
- 周末其他时段：60 分钟。
- 飞书批次发出后的前 6 小时：回复轮询保持 5 分钟。

## 上线门槛

至少完成三批影子验证：没有源文件写入、没有重复归档、时间戳顺序正确、私人内容不进入工作群。之后再依次打开 `enabled`、`mode=active`、`lark.enabled`，最后关闭 `lark.dry_run`。
