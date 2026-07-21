# speaker-review v2 数据协议

## 顶层结构

\`\`\`json
{
  "type": "speaker-review",
  "version": 2,
  "generated_at": "2026-01-15T10:30:00.000Z",
  "current": {},
  "batch": []
}
\`\`\`

- \`type\`：固定为 \`speaker-review\`。
- \`version\`：当前版本为 \`2\`。
- \`generated_at\`：ISO 8601 时间。
- \`current\`：当前会议，可为 \`null\`。
- \`batch\`：已确认会议数组。

导入时，工作台会把 \`current\` 与 \`batch\` 合并为待校对队列，并根据日期、时间和 \`file_stem\` 去重。

## 会议结构

\`\`\`json
{
  "meeting": "示例：产品周会",
  "date": "2026-01-15",
  "time": "09:30:12",
  "file_stem": "demo-product-weekly",
  "note": "特别一句：先确认验收标准，再决定排期。",
  "mappings": []
}
\`\`\`

- \`meeting\`：会议名称。
- \`date\`：\`YYYY-MM-DD\`。
- \`time\`：\`HH:mm:ss\`。
- \`file_stem\`：用于关联原始转写文件的稳定标识，不包含扩展名。
- \`note\`：会议最值得特别总结的一句话。
- \`mappings\`：说话人映射。

## 说话人映射

\`\`\`json
{
  "label": "Speaker 0",
  "name": "林青",
  "action": "replace",
  "confidence": "high",
  "note": "主持会议并安排后续动作。"
}
\`\`\`

### action

- \`replace\`：把原标签替换为确认后的姓名或角色。
- \`keep\`：保留当前标签或角色，不做确定性实名替换。
- \`ignore\`：环境音、设备播报或无法归属的碎片，不作为参会人处理。

### confidence

- \`high\`：有直接点名、用户确认或稳定身份链证据。
- \`medium\`：职责、上下文和表达方式高度吻合，但缺少直接点名。
- \`low\`：证据不足、标签串并或仅能确定角色。

用户主动把候选人改为另一个名字时，工作台自动将 \`action\` 设为 \`replace\`，将 \`confidence\` 设为 \`high\`。
