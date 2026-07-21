# Privacy

PlotLoop Speaker Review is local-first by design.

## 数据如何处理

- 页面不发起网络请求；
- 没有后端、登录、分析埋点或远程数据库；
- 导入内容只在浏览器内存与 \`localStorage\` 中处理；
- 导出由浏览器直接生成本地 JSON 文件；
- 点击左下角清空按钮可删除当前浏览器中的工作台数据。

## 仍需注意

本地优先不等于数据天然无风险。会议名称、参会人、判断依据和文件标识都可能是敏感信息：

- 不要把真实校对 JSON 提交到公开仓库；
- 不要把真实花名册写入 \`src/demo-data.js\`；
- 截图前检查会议列表、输入框、浏览器地址和下载文件名；
- 在共享电脑上使用后清空工作台数据；
- 对外演示只使用 \`examples/demo-speaker-review.json\`。

## 公开发布检查

提交前至少检查：

\`\`\`bash
git diff --check
npm test
git grep -n "/Users/"
git grep -n "generated_at" -- ':!examples/*' ':!docs/*' ':!src/demo-data.js'
\`\`\`

还应按团队自己的敏感词表扫描真实姓名、公司名、项目代号、邮箱、手机号、Token 和接口地址。

## 示例数据

仓库中的所有姓名、会议名称和判断依据均为虚构内容，仅用于展示数据结构与交互。
