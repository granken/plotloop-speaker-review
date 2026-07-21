(function () {
  "use strict";

  var core = window.PlotLoopSpeakerCore;
  var demo = window.PlotLoopSpeakerDemo;
  var STORAGE_KEY = "plotloop-speaker-review:v1";
  var state = {
    meetings: [],
    activeId: "",
    reviewed: {},
    filter: "all",
    roster: [],
    focusedNameInput: null
  };

  var elements = {};
  var toastTimer = 0;

  function byId(id) {
    return document.getElementById(id);
  }

  function make(tag, className, text) {
    var element = document.createElement(tag);
    if (className) {
      element.className = className;
    }
    if (text != null) {
      element.textContent = text;
    }
    return element;
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function initialize() {
    elements = {
      progressText: byId("progressText"),
      toast: byId("toast"),
      meetingList: byId("meetingList"),
      currentMoment: byId("currentMoment"),
      currentMeeting: byId("currentMeeting"),
      emptyState: byId("emptyState"),
      editorContent: byId("editorContent"),
      meetingInput: byId("meetingInput"),
      dateInput: byId("dateInput"),
      timeInput: byId("timeInput"),
      fileStemInput: byId("fileStemInput"),
      noteInput: byId("noteInput"),
      rosterInput: byId("rosterInput"),
      rosterCount: byId("rosterCount"),
      nameChips: byId("nameChips"),
      nameOptions: byId("nameOptions"),
      mappingList: byId("mappingList"),
      mappingCount: byId("mappingCount"),
      jsonOutput: byId("jsonOutput"),
      reviewedList: byId("reviewedList"),
      reviewedCount: byId("reviewedCount"),
      importDialog: byId("importDialog"),
      importText: byId("importText"),
      importError: byId("importError"),
      fileInput: byId("fileInput")
    };

    bindControls();

    if (!restore()) {
      loadPayload(demo, "已载入虚构示例");
      state.roster = ["林青", "顾川", "程澄", "产品同学", "研发同学", "客户代表"];
    }

    elements.rosterInput.value = state.roster.join("\n");
    renderAll();
    save();
  }

  function bindControls() {
    byId("importButton").addEventListener("click", openImportDialog);
    byId("loadDemoButton").addEventListener("click", function () {
      loadPayload(demo, "已载入虚构示例");
    });
    byId("confirmImportButton").addEventListener("click", importFromText);
    elements.fileInput.addEventListener("change", importFromFile);
    byId("acceptNextButton").addEventListener("click", acceptAndNext);
    byId("nextButton").addEventListener("click", nextMeeting);
    byId("acceptAllButton").addEventListener("click", acceptAll);
    byId("resetButton").addEventListener("click", resetWorkspace);
    byId("addMappingButton").addEventListener("click", addMapping);
    byId("copyButton").addEventListener("click", copyOutput);
    byId("downloadButton").addEventListener("click", downloadOutput);

    document.querySelectorAll("[data-filter]").forEach(function (button) {
      button.addEventListener("click", function () {
        state.filter = button.getAttribute("data-filter");
        document.querySelectorAll("[data-filter]").forEach(function (item) {
          item.classList.toggle("is-active", item === button);
        });
        renderMeetingList();
      });
    });

    document.querySelectorAll("[data-mobile-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        setMobilePanel(button.getAttribute("data-mobile-target"));
      });
    });

    [
      ["meetingInput", "meeting"],
      ["dateInput", "date"],
      ["timeInput", "time"],
      ["fileStemInput", "file_stem"],
      ["noteInput", "note"]
    ].forEach(function (entry) {
      elements[entry[0]].addEventListener("input", function () {
        var meeting = activeMeeting();
        if (!meeting) {
          return;
        }
        meeting[entry[1]] = elements[entry[0]].value;
        elements.currentMeeting.textContent = meeting.meeting || "未命名会议";
        elements.currentMoment.textContent = core.formatMoment(meeting);
        refreshReviewedSnapshot(meeting);
        renderMeetingList();
        renderOutput();
        save();
      });
    });

    elements.rosterInput.addEventListener("input", function () {
      state.roster = core.parseRoster(elements.rosterInput.value);
      renderRoster();
      save();
    });

    document.addEventListener("keydown", function (event) {
      if (!(event.metaKey || event.ctrlKey) || elements.importDialog.open) {
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        acceptAndNext();
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        nextMeeting();
      }
    });
  }

  function openImportDialog() {
    elements.importError.textContent = "";
    elements.fileInput.value = "";
    if (typeof elements.importDialog.showModal === "function") {
      elements.importDialog.showModal();
    } else {
      elements.importDialog.setAttribute("open", "");
    }
    elements.importText.focus();
  }

  function importFromText() {
    var raw = elements.importText.value.trim();
    if (!raw) {
      elements.importError.textContent = "请粘贴 JSON 或选择文件。";
      return;
    }
    try {
      loadPayload(JSON.parse(raw), "任务已导入");
      elements.importDialog.close();
      elements.importText.value = "";
    } catch (error) {
      elements.importError.textContent = error.message || "JSON 无法读取。";
    }
  }

  function importFromFile(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) {
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      elements.importText.value = String(reader.result || "");
      elements.importError.textContent = "";
    };
    reader.onerror = function () {
      elements.importError.textContent = "文件读取失败。";
    };
    reader.readAsText(file, "utf-8");
  }

  function loadPayload(payload, statusMessage) {
    var parsed = core.parseReviewPayload(clone(payload));
    state.meetings = parsed.meetings.map(function (meeting, index) {
      meeting._id = core.meetingKey(meeting) || "meeting-" + index;
      return meeting;
    });
    state.activeId = state.meetings.length ? state.meetings[0]._id : "";
    state.reviewed = {};
    state.focusedNameInput = null;
    renderAll();
    save();
    showToast(statusMessage);
  }

  function activeMeeting() {
    return state.meetings.find(function (meeting) {
      return meeting._id === state.activeId;
    }) || null;
  }

  function getMeeting(id) {
    return state.meetings.find(function (meeting) {
      return meeting._id === id;
    }) || null;
  }

  function selectMeeting(id, openReviewOnMobile) {
    if (!getMeeting(id)) {
      return;
    }
    state.activeId = id;
    state.focusedNameInput = null;
    fillEditor();
    renderMeetingList();
    renderOutput();
    save();
    if (openReviewOnMobile && window.matchMedia("(max-width: 980px)").matches) {
      setMobilePanel("review");
    }
  }

  function renderAll() {
    renderMeetingList();
    fillEditor();
    renderRoster();
    renderOutput();
  }

  function renderMeetingList() {
    elements.meetingList.replaceChildren();
    var visible = state.meetings.filter(function (meeting) {
      if (state.filter === "pending") {
        return !state.reviewed[meeting._id];
      }
      if (state.filter === "low") {
        return core.hasLowConfidence(meeting);
      }
      return true;
    });

    if (!visible.length) {
      elements.meetingList.appendChild(
        make("div", "empty-list", state.meetings.length ? "当前筛选下没有会议" : "尚未导入会议")
      );
    }

    visible.forEach(function (meeting) {
      var item = make("button", "meeting-item");
      item.type = "button";
      item.classList.toggle("is-active", meeting._id === state.activeId);
      item.classList.toggle("is-reviewed", Boolean(state.reviewed[meeting._id]));
      item.classList.toggle("has-low", core.hasLowConfidence(meeting));
      item.setAttribute("aria-pressed", meeting._id === state.activeId ? "true" : "false");

      var stateDot = make("span", "meeting-state");
      stateDot.setAttribute("aria-hidden", "true");
      var copyBlock = make("span", "meeting-copy");
      copyBlock.appendChild(make("span", "meeting-name", meeting.meeting));
      copyBlock.appendChild(make("span", "meeting-time", core.formatMoment(meeting)));
      if (meeting.note) {
        copyBlock.appendChild(make("span", "meeting-note", meeting.note));
      }
      item.appendChild(stateDot);
      item.appendChild(copyBlock);
      item.addEventListener("click", function () {
        selectMeeting(meeting._id, true);
      });
      elements.meetingList.appendChild(item);
    });

    var reviewedTotal = Object.keys(state.reviewed).length;
    elements.progressText.textContent = reviewedTotal + " / " + state.meetings.length + " 已确认";
    byId("acceptAllButton").disabled = !state.meetings.length;
  }

  function fillEditor() {
    var meeting = activeMeeting();
    var hasMeeting = Boolean(meeting);
    elements.emptyState.hidden = hasMeeting;
    elements.editorContent.hidden = !hasMeeting;
    byId("acceptNextButton").disabled = !hasMeeting;
    byId("nextButton").disabled = !hasMeeting;
    byId("addMappingButton").disabled = !hasMeeting;

    if (!meeting) {
      elements.currentMeeting.textContent = "选择一场会议";
      elements.currentMoment.textContent = "REVIEW";
      elements.mappingList.replaceChildren();
      return;
    }

    elements.currentMeeting.textContent = meeting.meeting;
    elements.currentMoment.textContent = core.formatMoment(meeting);
    elements.meetingInput.value = meeting.meeting;
    elements.dateInput.value = meeting.date;
    elements.timeInput.value = meeting.time;
    elements.fileStemInput.value = meeting.file_stem;
    elements.noteInput.value = meeting.note;
    renderMappings();
  }

  function renderRoster() {
    elements.rosterCount.textContent = state.roster.length + " 人";
    elements.nameChips.replaceChildren();
    elements.nameOptions.replaceChildren();

    state.roster.forEach(function (name) {
      var option = document.createElement("option");
      option.value = name;
      elements.nameOptions.appendChild(option);

      var chip = make("button", "name-chip", name);
      chip.type = "button";
      chip.title = "填入当前说话人";
      chip.addEventListener("click", function () {
        var target = state.focusedNameInput || elements.mappingList.querySelector(".mapping-name");
        if (!target) {
          return;
        }
        target.value = name;
        target.dispatchEvent(new Event("input", { bubbles: true }));
        target.focus();
      });
      elements.nameChips.appendChild(chip);
    });
  }

  function renderMappings() {
    var meeting = activeMeeting();
    elements.mappingList.replaceChildren();
    if (!meeting) {
      elements.mappingCount.textContent = "0 项";
      return;
    }

    meeting.mappings.forEach(function (mapping, index) {
      var row = make("div", "mapping-row");
      row.classList.toggle("is-low", mapping.confidence === "low");
      row.classList.toggle("is-replaced", mapping.action === "replace");

      var labelInput = mappingInput("原标签", mapping.label, "mapping-label");
      var nameInput = mappingInput("识别为", mapping.name, "mapping-name");
      nameInput.setAttribute("list", "nameOptions");
      var actionSelect = mappingSelect(
        "处理方式",
        [
          ["replace", "智能替换"],
          ["keep", "保留标签"],
          ["ignore", "忽略发言"]
        ],
        mapping.action,
        "mapping-action"
      );
      var confidenceSelect = mappingSelect(
        "置信度",
        [
          ["high", "高"],
          ["medium", "中"],
          ["low", "低"]
        ],
        mapping.confidence,
        "mapping-confidence"
      );
      var noteInput = mappingInput("判断依据", mapping.note, "mapping-note");

      var removeButton = make("button", "remove-mapping", "×");
      removeButton.type = "button";
      removeButton.title = "删除这个说话人";
      removeButton.setAttribute("aria-label", "删除这个说话人");

      labelInput.addEventListener("input", function () {
        mapping.label = labelInput.value;
        afterMappingChange(meeting, row);
      });
      nameInput.addEventListener("focus", function () {
        state.focusedNameInput = nameInput;
      });
      nameInput.addEventListener("input", function () {
        var decided = core.applyNameDecision(mapping, nameInput.value);
        Object.assign(mapping, decided);
        actionSelect.value = mapping.action;
        confidenceSelect.value = mapping.confidence;
        afterMappingChange(meeting, row);
      });
      actionSelect.addEventListener("change", function () {
        mapping.action = actionSelect.value;
        afterMappingChange(meeting, row);
      });
      confidenceSelect.addEventListener("change", function () {
        mapping.confidence = confidenceSelect.value;
        afterMappingChange(meeting, row);
      });
      noteInput.addEventListener("input", function () {
        mapping.note = noteInput.value;
        afterMappingChange(meeting, row);
      });
      removeButton.addEventListener("click", function () {
        meeting.mappings.splice(index, 1);
        state.focusedNameInput = null;
        refreshReviewedSnapshot(meeting);
        renderMappings();
        renderMeetingList();
        renderOutput();
        save();
      });

      row.appendChild(labelInput);
      row.appendChild(nameInput);
      row.appendChild(actionSelect);
      row.appendChild(confidenceSelect);
      row.appendChild(noteInput);
      row.appendChild(removeButton);
      elements.mappingList.appendChild(row);
    });

    elements.mappingCount.textContent = meeting.mappings.length + " 项";
  }

  function mappingInput(label, value, className) {
    var input = document.createElement("input");
    input.type = "text";
    input.value = value || "";
    input.className = className;
    input.placeholder = label;
    input.setAttribute("aria-label", label);
    input.autocomplete = "off";
    return input;
  }

  function mappingSelect(label, options, value, className) {
    var select = document.createElement("select");
    select.className = className;
    select.setAttribute("aria-label", label);
    options.forEach(function (optionData) {
      var option = document.createElement("option");
      option.value = optionData[0];
      option.textContent = optionData[1];
      select.appendChild(option);
    });
    select.value = value;
    return select;
  }

  function afterMappingChange(meeting, row) {
    row.classList.toggle(
      "is-low",
      row.querySelector(".mapping-confidence").value === "low"
    );
    row.classList.toggle(
      "is-replaced",
      row.querySelector(".mapping-action").value === "replace"
    );
    refreshReviewedSnapshot(meeting);
    renderMeetingList();
    renderOutput();
    save();
  }

  function addMapping() {
    var meeting = activeMeeting();
    if (!meeting) {
      return;
    }
    meeting.mappings.push(
      core.normalizeMapping({
        label: "Speaker " + meeting.mappings.length,
        name: "",
        action: "keep",
        confidence: "low",
        note: ""
      })
    );
    renderMappings();
    renderMeetingList();
    renderOutput();
    save();
    var inputs = elements.mappingList.querySelectorAll(".mapping-name");
    if (inputs.length) {
      inputs[inputs.length - 1].focus();
    }
  }

  function refreshReviewedSnapshot(meeting) {
    if (state.reviewed[meeting._id]) {
      state.reviewed[meeting._id] = core.serializeMeeting(meeting);
    }
  }

  function acceptCurrent() {
    var meeting = activeMeeting();
    if (!meeting) {
      return false;
    }
    state.reviewed[meeting._id] = core.serializeMeeting(meeting);
    renderMeetingList();
    renderOutput();
    save();
    return true;
  }

  function acceptAndNext() {
    if (!acceptCurrent()) {
      return;
    }
    showToast("当前会议已确认");
    nextMeeting(true);
  }

  function nextMeeting(preferPending) {
    if (!state.meetings.length) {
      return;
    }
    var currentIndex = state.meetings.findIndex(function (meeting) {
      return meeting._id === state.activeId;
    });
    var next = null;
    var offset;

    for (offset = 1; offset <= state.meetings.length; offset += 1) {
      var candidate = state.meetings[(currentIndex + offset) % state.meetings.length];
      if (!preferPending || !state.reviewed[candidate._id]) {
        next = candidate;
        break;
      }
    }
    if (!next) {
      next = state.meetings[(currentIndex + 1) % state.meetings.length];
    }
    selectMeeting(next._id, false);
  }

  function acceptAll() {
    state.meetings.forEach(function (meeting) {
      state.reviewed[meeting._id] = core.serializeMeeting(meeting);
    });
    renderMeetingList();
    renderOutput();
    save();
    showToast("全部会议已按当前建议确认");
  }

  function resetWorkspace() {
    if (!window.confirm("清空当前会议、校对结果和本地常用人？")) {
      return;
    }
    state.meetings = [];
    state.activeId = "";
    state.reviewed = {};
    state.roster = [];
    state.focusedNameInput = null;
    elements.rosterInput.value = "";
    renderAll();
    save();
    showToast("本地数据已清空");
  }

  function renderOutput() {
    var reviewedMeetings = state.meetings
      .filter(function (meeting) {
        return Boolean(state.reviewed[meeting._id]);
      })
      .map(function (meeting) {
        return state.reviewed[meeting._id];
      });
    var payload = core.buildPayload(activeMeeting(), reviewedMeetings);
    elements.jsonOutput.value = JSON.stringify(payload, null, 2);
    elements.reviewedCount.textContent = reviewedMeetings.length + " 场";
    elements.reviewedList.replaceChildren();

    if (!reviewedMeetings.length) {
      elements.reviewedList.appendChild(make("div", "empty-list", "确认后的会议会出现在这里"));
    }

    state.meetings.forEach(function (meeting) {
      if (!state.reviewed[meeting._id]) {
        return;
      }
      var item = make("div", "reviewed-item");
      var loadButton = document.createElement("button");
      loadButton.type = "button";
      loadButton.appendChild(make("strong", "", meeting.meeting));
      loadButton.appendChild(make("span", "", core.formatMoment(meeting)));
      loadButton.addEventListener("click", function () {
        selectMeeting(meeting._id, true);
      });
      var removeButton = make("button", "remove-mapping", "×");
      removeButton.type = "button";
      removeButton.title = "移出已确认";
      removeButton.setAttribute("aria-label", "移出已确认");
      removeButton.addEventListener("click", function () {
        delete state.reviewed[meeting._id];
        renderMeetingList();
        renderOutput();
        save();
      });
      item.appendChild(loadButton);
      item.appendChild(removeButton);
      elements.reviewedList.appendChild(item);
    });
  }

  async function copyOutput() {
    var text = elements.jsonOutput.value;
    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      elements.jsonOutput.focus();
      elements.jsonOutput.select();
      document.execCommand("copy");
      window.getSelection().removeAllRanges();
    }
    showToast("JSON 已复制");
  }

  function downloadOutput() {
    var blob = new Blob([elements.jsonOutput.value], {
      type: "application/json;charset=utf-8"
    });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "speaker-review-" + new Date().toISOString().slice(0, 10) + ".json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showToast("JSON 已下载");
  }

  function setMobilePanel(target) {
    document.querySelectorAll("[data-panel]").forEach(function (panel) {
      panel.classList.toggle("is-mobile-active", panel.getAttribute("data-panel") === target);
    });
    document.querySelectorAll("[data-mobile-target]").forEach(function (button) {
      button.classList.toggle(
        "is-active",
        button.getAttribute("data-mobile-target") === target
      );
    });
  }

  function save() {
    var snapshot = {
      meetings: state.meetings,
      activeId: state.activeId,
      reviewed: state.reviewed,
      filter: state.filter,
      roster: state.roster
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  }

  function restore() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        return false;
      }
      var snapshot = JSON.parse(raw);
      state.meetings = Array.isArray(snapshot.meetings)
        ? snapshot.meetings.map(reviveMeeting)
        : [];
      state.activeId = getRestoredActiveId(snapshot.activeId);
      state.reviewed = snapshot.reviewed && typeof snapshot.reviewed === "object"
        ? snapshot.reviewed
        : {};
      state.filter = ["all", "pending", "low"].indexOf(snapshot.filter) >= 0
        ? snapshot.filter
        : "all";
      state.roster = Array.isArray(snapshot.roster)
        ? core.parseRoster(snapshot.roster.join("\n"))
        : [];

      document.querySelectorAll("[data-filter]").forEach(function (button) {
        button.classList.toggle(
          "is-active",
          button.getAttribute("data-filter") === state.filter
        );
      });
      return true;
    } catch (error) {
      localStorage.removeItem(STORAGE_KEY);
      return false;
    }
  }

  function reviveMeeting(source, index) {
    var meeting = core.normalizeMeeting(source);
    meeting._id = source._id || core.meetingKey(meeting) || "meeting-" + index;
    meeting.mappings = meeting.mappings.map(function (mapping, mappingIndex) {
      var saved = source.mappings && source.mappings[mappingIndex];
      if (saved) {
        mapping._suggestedName = saved._suggestedName != null
          ? saved._suggestedName
          : mapping._suggestedName;
        mapping._suggestedAction = saved._suggestedAction || mapping._suggestedAction;
        mapping._suggestedConfidence =
          saved._suggestedConfidence || mapping._suggestedConfidence;
      }
      return mapping;
    });
    return meeting;
  }

  function getRestoredActiveId(activeId) {
    if (state.meetings.some(function (meeting) { return meeting._id === activeId; })) {
      return activeId;
    }
    return state.meetings.length ? state.meetings[0]._id : "";
  }

  function showToast(message) {
    window.clearTimeout(toastTimer);
    elements.toast.textContent = message || "";
    toastTimer = window.setTimeout(function () {
      elements.toast.textContent = "";
    }, 2400);
  }

  window.addEventListener("DOMContentLoaded", initialize);
})();
