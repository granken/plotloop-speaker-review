<p align="center">
  <img src="./assets/plotloop-logo.svg" alt="plotloop" width="320">
</p>

<h1 align="center">PlotLoop Speaker Review</h1>

<p align="center">
  A local-first workbench for turning uncertain speaker labels into reviewed, reusable meeting data.
</p>

<p align="center">
  <a href="https://granken.github.io/plotloop-speaker-review/"><strong>在线体验</strong></a>
  ·
  <a href="./docs/RELEASE_NOTES_0.5.0.zh-CN.md">0.5.0 升级说明</a>
  ·
  <a href="./docs/DATA_FORMAT.md">数据协议</a>
  ·
  <a href="./PRIVACY.md">隐私说明</a>
</p>

一个用于会议文字稿说话人校对的本地网页工具。把模型给出的 \`Speaker 0\`、\`讲话人 1\` 等候选标签集中导入，快速确认、修改并导出统一的 \`speaker-review v2\` JSON。

![PlotLoop Speaker Review workbench](./assets/workbench-preview.png)

## 为什么做

说话人识别通常不是一次推理就结束，而是一个闭环：

1. 模型根据上下文提出候选人和置信度。
2. 熟悉参会人的用户快速确认或纠正。
3. 确认结果写回转写、总结和人物记忆。
4. 新的确认继续提高下一轮识别质量。

PlotLoop Speaker Review 负责第 2 步，并把第 3、4 步需要的结构化结果交出去。

## 特点

- **快审**：会议队列与宽校对区组成主界面；支持“确认并下一场”和整批按建议确认。
- **自动联动**：把候选人改成另一个名字时，处理方式自动设为 \`replace\`，置信度自动设为 \`high\`。
- **时间到秒**：同时展示日期和时分秒，便于区分同一天的多场会议。
- **点选联系人**：点击姓名字段直接打开“最近使用 + 常用联系人”选择层，手机远程操作不依赖键盘输入。
- **联系人自学习**：人工改名或确认后，真实姓名自动写入本机私有联系人库；下次打开工作台即可直接点选，公开仓不包含这些姓名。
- **紧凑判断区**：每个说话人默认只占一行，判断依据和删除操作按需展开。
- **信息按需出现**：切换会议时短暂展示一句话总结；会议信息收在标题中，JSON 结果默认收进抽屉。
- **就近连续确认**：主操作紧贴会议标题和一句总结，固定按“确认并下一场、跳过”的顺序呈现，手机远程操作也无需把光标移到页面角落。
- **低置信筛选**：一键只看仍需人工判断的会议。
- **飞书确认卡片**：自动化批次使用 Card 2.0 按会议折叠展示，高疑惑优先；大批次自动拆卡，发送失败自动退回纯文字。
- **零模型本地回写**：通过本机服务打开时，可把已确认批次直接写回转写、总结、索引和完成信号；这一步只做结构化校验与文本替换，不调用大模型。在线演示和强制示例模式不会显示该入口。
- **本地优先**：静态审阅模式没有账号、埋点或远程数据请求；会议数据只保存在当前浏览器或用户配置的本地目录。
- **直接打开**：无需安装依赖，双击 \`index.html\` 即可使用。

## 快速开始

直接打开 [在线体验版](https://granken.github.io/plotloop-speaker-review/) 即可使用完全虚构的示例数据，无需安装。

需要在本机使用私人联系人和待确认数据时，可以直接打开 [index.html](./index.html)。

也可以启动本地静态服务：

\`\`\`bash
npm run serve
\`\`\`

然后访问 \`http://localhost:4173\`。

运行核心逻辑测试：

\`\`\`bash
npm test
\`\`\`

## 使用流程

1. 点击“导入”，粘贴或选择 \`speaker-review\` JSON。
2. 浏览会议的一句话特别总结、时间和候选映射。
3. 确认建议，或点击姓名从常用联系人中选择正确的人。
4. 点击“确认并下一场”。
5. 本地服务模式点击“确认并回写”，或在静态模式复制/下载右侧 JSON 交给后续流程。

完整格式见 [数据协议](./docs/DATA_FORMAT.md)，可直接使用 [脱敏示例](./examples/demo-speaker-review.json) 测试。

## 项目边界

静态工作台本身不负责：

- 音频转写；
- 声纹注册或声纹比对；
- 自动修改原始文字稿；
- 把会议数据上传到云端；
- 替代人工处理低置信、多说话人串并等复杂情况。

可选的 `automation/` 适配器在用户明确配置后负责发现、分析、飞书确认和本地写回；它默认关闭，不改变静态工作台的简单性，也不会绕过人工确认。

本地写回分成两段：说话人初判仍可使用模型；人工已经拍板后的 JSON 校验、姓名替换、时间戳保留、索引更新和联系人沉淀均由确定性脚本完成，不再重复消耗模型算力。

## 技术结构

\`\`\`text
index.html          页面结构
src/styles.css      三栏工作台与移动端视图
src/core.js         数据解析、决策联动和导出协议
src/bootstrap.js    本机私人数据与公开演示数据的加载边界
src/app.js          浏览器状态、交互与本地存储
src/demo-data.js    虚构演示数据
automation/         可选录音发现、分析、飞书确认与写回
scripts/            本地服务、发布检查和 launchd 辅助工具
tests/              网页核心测试
\`\`\`

项目使用原生 HTML、CSS 和 JavaScript，不需要构建步骤或第三方运行时依赖。

## 隐私

会议标题、人名和判断依据都可能是敏感信息。公开提交前请阅读 [PRIVACY.md](./PRIVACY.md)。本仓库只包含虚构样例，不包含真实花名册、会议记录、本机路径或历史校对结果。

## 可选录音自动化

仓库还包含一套纯 Python 标准库实现的可选流程：发现 YoooClaw 新录音、热词校正、Codex 说话人初判、飞书确认，以及保留时间戳的归档。它默认关闭并运行在影子模式；本机路径、花名册、身份、群 ID、逐字稿和运行状态都保存在 Git 仓库之外。

详见 [录音自动化与飞书确认](./docs/AUTOMATION.zh-CN.md) 和 `automation/config.example.json`。

提交公开版本前运行：

```bash
npm run test:release
```

该命令会执行网页与自动化测试，并检查候选提交文件中是否混入本地数据、备份文件、绝对用户目录或真实飞书标识。完整步骤见 [发布前检查清单](./docs/RELEASE_CHECKLIST.md)。

## 项目信息

产品定位、命名理由、范围和路线图见 [PROJECT_BRIEF.md](./docs/PROJECT_BRIEF.md)。

## License

MIT
