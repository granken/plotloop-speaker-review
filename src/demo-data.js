window.PlotLoopSpeakerDemo = {
  type: "speaker-review",
  version: 2,
  generated_at: "2026-01-15T10:30:00.000Z",
  current: {
    meeting: "示例：产品周会与发布节奏确认",
    date: "2026-01-15",
    time: "09:30:12",
    file_stem: "demo-product-weekly",
    note: "特别一句：先确认用户价值与验收标准，再决定功能排期。",
    mappings: [
      {
        label: "Speaker 0",
        name: "林青",
        action: "replace",
        confidence: "high",
        note: "主持会议并安排产品节奏。"
      },
      {
        label: "Speaker 1",
        name: "产品同学",
        action: "keep",
        confidence: "medium",
        note: "汇报需求与交付风险，未出现实名。"
      }
    ]
  },
  batch: [
    {
      meeting: "示例：客户访谈复盘",
      date: "2026-01-15",
      time: "14:05:48",
      file_stem: "demo-customer-interview",
      note: "特别一句：客户真正需要的是可追踪的结果，而不是更多配置项。",
      mappings: [
        {
          label: "speakerId 0",
          name: "顾川",
          action: "replace",
          confidence: "medium",
          note: "负责追问客户的使用路径。"
        },
        {
          label: "speakerId 1",
          name: "客户代表",
          action: "keep",
          confidence: "low",
          note: "未出现姓名，需要人工确认。"
        },
        {
          label: "speakerId 2",
          name: "背景音/环境音",
          action: "ignore",
          confidence: "high",
          note: "设备播报，不属于参会人。"
        }
      ]
    },
    {
      meeting: "示例：技术方案评审",
      date: "2026-01-16",
      time: "11:20:03",
      file_stem: "demo-technical-review",
      note: "特别一句：先跑通小规模闭环，再根据失败样本补规则。",
      mappings: [
        {
          label: "Speaker 0",
          name: "程澄",
          action: "replace",
          confidence: "high",
          note: "提出评审结论和后续动作。"
        },
        {
          label: "Speaker 1",
          name: "研发同学",
          action: "keep",
          confidence: "low",
          note: "说明实现限制，未出现实名。"
        }
      ]
    }
  ]
};
