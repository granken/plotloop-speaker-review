(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.PlotLoopSpeakerCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ACTIONS = ["replace", "keep", "ignore"];
  const CONFIDENCES = ["high", "medium", "low"];

  function clean(value) {
    return value == null ? "" : String(value).trim();
  }

  function validChoice(value, choices, fallback) {
    var normalized = clean(value);
    return choices.indexOf(normalized) >= 0 ? normalized : fallback;
  }

  function normalizeMapping(mapping) {
    var source = mapping || {};
    var name = clean(source.name);
    var action = validChoice(source.action, ACTIONS, "keep");
    var confidence = validChoice(source.confidence, CONFIDENCES, "low");

    return {
      label: clean(source.label),
      name: name,
      action: action,
      confidence: confidence,
      note: clean(source.note),
      _suggestedName: name,
      _suggestedAction: action,
      _suggestedConfidence: confidence
    };
  }

  function normalizeMeeting(meeting) {
    var source = meeting || {};
    return {
      meeting: clean(source.meeting || source.title) || "未命名会议",
      date: clean(source.date),
      time: clean(source.time),
      file_stem: clean(source.file_stem || source.meeting || source.title) || "untitled",
      note: clean(source.note),
      mappings: Array.isArray(source.mappings)
        ? source.mappings.map(normalizeMapping)
        : []
    };
  }

  function meetingKey(meeting) {
    var item = normalizeMeeting(meeting);
    return [item.date, item.time, item.file_stem].join("::");
  }

  function parseReviewPayload(input) {
    var payload = typeof input === "string" ? JSON.parse(input) : input;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("需要一个 speaker-review JSON 对象。");
    }
    if (payload.type && payload.type !== "speaker-review") {
      throw new Error("type 必须是 speaker-review。");
    }

    var sourceMeetings = [];
    if (payload.current) {
      sourceMeetings.push(payload.current);
    }
    if (Array.isArray(payload.batch)) {
      sourceMeetings = sourceMeetings.concat(payload.batch);
    }
    if (!sourceMeetings.length && Array.isArray(payload.meetings)) {
      sourceMeetings = sourceMeetings.concat(payload.meetings);
    }
    if (!sourceMeetings.length) {
      throw new Error("没有找到 current、batch 或 meetings 中的会议数据。");
    }

    var seen = Object.create(null);
    var meetings = [];
    sourceMeetings.forEach(function (source) {
      var item = normalizeMeeting(source);
      var key = meetingKey(item);
      if (!seen[key]) {
        seen[key] = true;
        meetings.push(item);
      }
    });
    meetings.sort(function (a, b) {
      return (a.date + "T" + (a.time || "00:00:00")).localeCompare(
        b.date + "T" + (b.time || "00:00:00")
      );
    });

    return {
      generatedAt: clean(payload.generated_at),
      meetings: meetings
    };
  }

  function applyNameDecision(mapping, nextName) {
    var item = Object.assign({}, mapping);
    var selectedName = clean(nextName);
    item.name = selectedName;

    if (selectedName && selectedName !== clean(item._suggestedName)) {
      item.action = "replace";
      item.confidence = "high";
    } else {
      item.action = validChoice(item._suggestedAction, ACTIONS, "keep");
      item.confidence = validChoice(item._suggestedConfidence, CONFIDENCES, "low");
    }
    return item;
  }

  function serializeMapping(mapping) {
    return {
      label: clean(mapping.label),
      name: clean(mapping.name),
      action: validChoice(mapping.action, ACTIONS, "keep"),
      confidence: validChoice(mapping.confidence, CONFIDENCES, "low"),
      note: clean(mapping.note)
    };
  }

  function serializeMeeting(meeting) {
    var item = normalizeMeeting(meeting);
    return {
      meeting: item.meeting,
      date: item.date,
      time: item.time,
      file_stem: item.file_stem,
      note: item.note,
      mappings: (meeting.mappings || []).map(serializeMapping)
    };
  }

  function buildPayload(activeMeeting, reviewedMeetings, now) {
    var reviewed = Array.isArray(reviewedMeetings) ? reviewedMeetings : [];
    return {
      type: "speaker-review",
      version: 2,
      generated_at: (now || new Date()).toISOString(),
      current: activeMeeting ? serializeMeeting(activeMeeting) : null,
      batch: reviewed.map(serializeMeeting)
    };
  }

  function parseRoster(value) {
    var seen = Object.create(null);
    return clean(value)
      .split(/[\n,，、;；]+/)
      .map(clean)
      .filter(function (name) {
        if (!name || seen[name]) {
          return false;
        }
        seen[name] = true;
        return true;
      });
  }

  function formatMoment(meeting) {
    var date = clean(meeting.date) || "日期待补";
    var time = clean(meeting.time) || "时间待补";
    return date + " " + time;
  }

  function hasLowConfidence(meeting) {
    return (meeting.mappings || []).some(function (mapping) {
      return mapping.confidence === "low";
    });
  }

  return {
    ACTIONS: ACTIONS,
    CONFIDENCES: CONFIDENCES,
    applyNameDecision: applyNameDecision,
    buildPayload: buildPayload,
    formatMoment: formatMoment,
    hasLowConfidence: hasLowConfidence,
    meetingKey: meetingKey,
    normalizeMapping: normalizeMapping,
    normalizeMeeting: normalizeMeeting,
    parseReviewPayload: parseReviewPayload,
    parseRoster: parseRoster,
    serializeMeeting: serializeMeeting
  };
});
