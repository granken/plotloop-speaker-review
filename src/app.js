(function () {
  "use strict";

  var core = window.PlotLoopSpeakerCore;
  var demo = window.PlotLoopSpeakerDemo;
  var localPayload = window.PlotLoopSpeakerLocal;
  var localConfig = window.PlotLoopSpeakerLocalConfig || {};
  var forceDemo = window.PlotLoopSpeakerForceDemo === true;
  var localSubmitEnabled =
    !forceDemo &&
    window.location.protocol === "http:" &&
    (window.location.hostname === "127.0.0.1" ||
      window.location.hostname === "localhost" ||
      window.location.hostname === "[::1]");
  var STORAGE_KEY = "plotloop-speaker-review:v1";
  var state = {
    meetings: [],
    activeId: "",
    reviewed: {},
    filter: "all",
    roster: [],
    recentNames: [],
    rosterVersion: "",
    taskGeneratedAt: ""
  };

  let elements = {};
  let toastTimer = 0;
  let summaryTimer = 0;
  let namePickerTarget = null;

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
      summaryPeek: byId("summaryPeek"),
      meetingMetaPopover: byId("meetingMetaPopover"),
      meetingDetailsButton: byId("meetingDetailsButton"),
      summaryToggleButton: byId("summaryToggleButton"),
      rosterInput: byId("rosterInput"),
      rosterCount: byId("rosterCount"),
      mappingList: byId("mappingList"),
      mappingCount: byId("mappingCount"),
      jsonOutput: byId("jsonOutput"),
      reviewedList: byId("reviewedList"),
      reviewedCount: byId("reviewedCount"),
      reviewPosition: byId("reviewPosition"),
      importDialog: byId("importDialog"),
      importText: byId("importText"),
      importError: byId("importError"),
      fileInput: byId("fileInput"),
      rosterDialog: byId("rosterDialog"),
      namePickerDialog: byId("namePickerDialog"),
      namePickerLabel: byId("namePickerLabel"),
      recentNameSection: byId("recentNameSection"),
      recentNameList: byId("recentNameList"),
      namePickerList: byId("namePickerList"),
      namePickerEmpty: byId("namePickerEmpty"),
      customNameInput: byId("customNameInput"),
      useCustomNameButton: byId("useCustomNameButton"),
      outputPanel: byId("outputPanel"),
      outputToggleButton: byId("outputToggleButton")
    };

    bindControls();

    var restored = forceDemo ? false : restore();
    if (forceDemo) {
      loadPayload(demo, "已载入隔离的虚构示例");
      state.roster = ["林青", "顾川", "程澄", "产品同学", "研发同学", "客户代表"];
    } else if (localPayload && state.taskGeneratedAt !== localPayload.generated_at) {
      loadPayload(localPayload, "已载入本地待确认任务");
    } else if (!restored) {
      loadPayload(demo, "已载入虚构示例");
      state.roster = ["林青", "顾川", "程澄", "产品同学", "研发同学", "客户代表"];
    }

    if (
      !forceDemo &&
      Array.isArray(localConfig.roster) &&
      localConfig.roster.length &&
      state.rosterVersion !== localConfig.version
    ) {
      state.roster = core.parseRoster(localConfig.roster.join("\n"));
      state.rosterVersion = localConfig.version || "local";
    }

    elements.rosterInput.value = state.roster.join("\n");
    renderAll();
    save();
    setOutputOpen(false);
    if (activeMeeting()) {
      setSummaryOpen(true, true);
    }
  }

  function bindControls() {
    var submitButtons = [byId("submitConfirmButton"), byId("submitQuickButton")];
    submitButtons.forEach(function (button) {
      button.hidden = !localSubmitEnabled;
    });
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
    byId("manageRosterButton").addEventListener("click", openRosterDialog);
    byId("copyButton").addEventListener("click", copyOutput);
    byId("copyQuickButton").addEventListener("click", copyOutput);
    byId("downloadButton").addEventListener("click", downloadOutput);
    if (localSubmitEnabled) {
      byId("submitConfirmButton").addEventListener("click", submitConfirm);
      byId("submitQuickButton").addEventListener("click", submitConfirm);
    }
    byId("outputToggleButton").addEventListener("click", function () {
      if (window.matchMedia("(max-width: 980px)").matches) {
        setMobilePanel("output");
        return;
      }
      setOutputOpen(!elements.outputPanel.classList.contains("is-open"));
    });
    byId("closeOutputButton").addEventListener("click", closeOutput);
    byId("summaryToggleButton").addEventListener("click", function () {
      setSummaryOpen(elements.summaryPeek.hidden, false);
    });
    byId("closeSummaryButton").addEventListener("click", function () {
      setSummaryOpen(false, false);
    });
    byId("meetingDetailsButton").addEventListener("click", function () {
      setMeetingDetailsOpen(elements.meetingMetaPopover.hidden);
    });
    byId("closeMeetingDetailsButton").addEventListener("click", function () {
      setMeetingDetailsOpen(false);
    });
    byId("closeNamePickerButton").addEventListener("click", closeNamePicker);
    byId("manageRosterFromPickerButton").addEventListener("click", function () {
      closeNamePicker();
      openRosterDialog();
    });
    elements.useCustomNameButton.addEventListener("click", function () {
      applyPickedName(elements.customNameInput.value);
    });
    elements.customNameInput.addEventListener("input", function () {
      elements.useCustomNameButton.disabled = !elements.customNameInput.value.trim();
      renderNamePicker(elements.customNameInput.value);
    });
    elements.customNameInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && elements.customNameInput.value.trim()) {
        event.preventDefault();
        applyPickedName(elements.customNameInput.value);
      }
    });
    elements.namePickerDialog.addEventListener("close", function () {
      namePickerTarget = null;
    });
    elements.noteInput.addEventListener("focus", function () {
      window.clearTimeout(summaryTimer);
    });
    document.addEventListener("pointerdown", function (event) {
      if (
        !elements.summaryPeek.hidden &&
        !elements.summaryPeek.contains(event.target) &&
        !elements.summaryToggleButton.contains(event.target)
      ) {
        setSummaryOpen(false, false);
      }
    });

    var filterButtons = document.querySelectorAll("[data-filter]");
    filterButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        state.filter = button.getAttribute("data-filter");
        filterButtons.forEach(function (item) {
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
      if (elements.namePickerDialog.open) {
        renderNamePicker(elements.customNameInput.value);
      }
      save();
    });

    document.addEventListener("keydown", function (event) {
      if (
        event.key === "Escape" &&
        !elements.importDialog.open &&
        !elements.rosterDialog.open &&
        !elements.namePickerDialog.open
      ) {
        setSummaryOpen(false, false);
        setMeetingDetailsOpen(false);
        setOutputOpen(false);
        return;
      }
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

  function openRosterDialog() {
    if (typeof elements.rosterDialog.showModal === "function") {
      elements.rosterDialog.showModal();
    } else {
      elements.rosterDialog.setAttribute("open", "");
    }
    elements.rosterInput.focus();
  }

  function setSummaryOpen(open, autoClose) {
    window.clearTimeout(summaryTimer);
    elements.summaryPeek.hidden = !open;
    elements.summaryToggleButton.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      setMeetingDetailsOpen(false);
    }
    if (open && autoClose) {
      summaryTimer = window.setTimeout(function () {
        setSummaryOpen(false, false);
      }, 5200);
    }
  }

  function setMeetingDetailsOpen(open) {
    elements.meetingMetaPopover.hidden = !open;
    elements.meetingDetailsButton.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      setSummaryOpen(false, false);
    }
  }

  function setOutputOpen(open) {
    elements.outputPanel.classList.toggle("is-open", open);
    elements.outputPanel.setAttribute("aria-hidden", open ? "false" : "true");
    elements.outputToggleButton.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function closeOutput() {
    if (window.matchMedia("(max-width: 980px)").matches) {
      setMobilePanel("review");
      return;
    }
    setOutputOpen(false);
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
    state.taskGeneratedAt = parsed.generatedAt;
    state.activeId = state.meetings.length ? state.meetings[0]._id : "";
    state.reviewed = {};
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
    setMeetingDetailsOpen(false);
    fillEditor();
    renderMeetingList();
    renderOutput();
    save();
    setSummaryOpen(true, true);
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
      item.appendChild(stateDot);
      item.appendChild(copyBlock);
      item.addEventListener("click", function () {
        selectMeeting(meeting._id, true);
      });
      elements.meetingList.appendChild(item);
    });

    var reviewedTotal = Object.keys(state.reviewed).length;
    elements.progressText.textContent = reviewedTotal + " / " + state.meetings.length + " 已确认";
    renderReviewPosition();
    byId("acceptAllButton").disabled = !state.meetings.length;
  }

  function renderReviewPosition() {
    var currentIndex = state.meetings.findIndex(function (meeting) {
      return meeting._id === state.activeId;
    });
    elements.reviewPosition.textContent = state.meetings.length
      ? currentIndex + 1 + " / " + state.meetings.length
      : "0 / 0";
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
  }

  function renderMappings() {
    var meeting = activeMeeting();
    elements.mappingList.replaceChildren();
    if (!meeting) {
      elements.mappingCount.textContent = "0 项";
      return;
    }

    meeting.mappings.forEach(function (mapping, index) {
      var card = make("div", "mapping-card");
      var row = make("div", "mapping-row");
      card.classList.toggle("is-low", mapping.confidence === "low");
      card.classList.toggle("is-replaced", mapping.action === "replace");

      var labelInput = mappingInput("原标签", mapping.label, "mapping-label");
      labelInput.title = mapping.label;
      var nameButton = make("button", "mapping-name");
      nameButton.type = "button";
      nameButton.title = mapping.name || "选择说话人";
      nameButton.setAttribute("aria-label", "识别为，当前 " + (mapping.name || "未填写"));
      nameButton.appendChild(make("span", "mapping-name-value", mapping.name || "选择说话人"));
      nameButton.appendChild(make("span", "mapping-name-arrow", "⌄"));
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
      var noteButton = make("button", "mapping-note-toggle", "依据");
      noteButton.type = "button";
      noteButton.title = mapping.note || "补充判断依据";
      noteButton.setAttribute("aria-expanded", "false");
      var noteEditor = make("div", "mapping-note-editor");
      noteEditor.hidden = true;
      noteEditor.appendChild(noteInput);
      var mobileRemoveButton = make(
        "button",
        "button mobile-remove-mapping",
        "删除此说话人"
      );
      mobileRemoveButton.type = "button";
      noteEditor.appendChild(mobileRemoveButton);

      var removeButton = make("button", "remove-mapping", "×");
      removeButton.type = "button";
      removeButton.title = "删除这个说话人";
      removeButton.setAttribute("aria-label", "删除这个说话人");

      labelInput.addEventListener("input", function () {
        mapping.label = labelInput.value;
        afterMappingChange(meeting, card);
      });
      nameButton.addEventListener("click", function () {
        openNamePicker(meeting, index);
      });
      actionSelect.addEventListener("change", function () {
        mapping.action = actionSelect.value;
        afterMappingChange(meeting, card);
      });
      confidenceSelect.addEventListener("change", function () {
        mapping.confidence = confidenceSelect.value;
        afterMappingChange(meeting, card);
      });
      noteInput.addEventListener("input", function () {
        mapping.note = noteInput.value;
        noteButton.title = mapping.note || "补充判断依据";
        afterMappingChange(meeting, card);
      });
      noteButton.addEventListener("click", function () {
        var open = noteEditor.hidden;
        noteEditor.hidden = !open;
        noteButton.setAttribute("aria-expanded", open ? "true" : "false");
        if (open) {
          noteInput.focus();
        }
      });
      function removeCurrentMapping() {
        meeting.mappings.splice(index, 1);
        refreshReviewedSnapshot(meeting);
        renderMappings();
        renderMeetingList();
        renderOutput();
        save();
      }
      removeButton.addEventListener("click", removeCurrentMapping);
      mobileRemoveButton.addEventListener("click", removeCurrentMapping);

      row.appendChild(labelInput);
      row.appendChild(nameButton);
      row.appendChild(actionSelect);
      row.appendChild(confidenceSelect);
      row.appendChild(noteButton);
      row.appendChild(removeButton);
      card.appendChild(row);
      card.appendChild(noteEditor);
      elements.mappingList.appendChild(card);
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

  function afterMappingChange(meeting, card) {
    card.classList.toggle(
      "is-low",
      card.querySelector(".mapping-confidence").value === "low"
    );
    card.classList.toggle(
      "is-replaced",
      card.querySelector(".mapping-action").value === "replace"
    );
    refreshReviewedSnapshot(meeting);
    renderMeetingList();
    renderOutput();
    save();
  }

  function openNamePicker(meeting, mappingIndex) {
    var mapping = meeting.mappings[mappingIndex];
    namePickerTarget = { meetingId: meeting._id, mappingIndex: mappingIndex };
    elements.namePickerLabel.textContent = mapping.label + " · 当前 " + (mapping.name || "未填写");
    elements.customNameInput.value = "";
    elements.useCustomNameButton.disabled = true;
    renderNamePicker("");
    if (typeof elements.namePickerDialog.showModal === "function") {
      elements.namePickerDialog.showModal();
    } else {
      elements.namePickerDialog.setAttribute("open", "");
    }
  }

  function closeNamePicker() {
    namePickerTarget = null;
    if (typeof elements.namePickerDialog.close === "function") {
      elements.namePickerDialog.close();
    } else {
      elements.namePickerDialog.removeAttribute("open");
    }
  }

  function renderNamePicker(query) {
    var targetMeeting = namePickerTarget ? getMeeting(namePickerTarget.meetingId) : null;
    var targetMapping = targetMeeting
      ? targetMeeting.mappings[namePickerTarget.mappingIndex]
      : null;
    var currentName = targetMapping ? targetMapping.name : "";
    var normalizedQuery = String(query || "").trim().toLowerCase();
    var recent = uniqueNames([currentName].concat(state.recentNames)).filter(matchesName);
    var recentLookup = Object.create(null);
    recent.forEach(function (name) { recentLookup[name] = true; });
    var roster = state.roster.filter(function (name) {
      return !recentLookup[name] && matchesName(name);
    });

    elements.recentNameList.replaceChildren();
    recent.forEach(function (name) {
      elements.recentNameList.appendChild(nameChoiceButton(name, name === currentName));
    });
    elements.recentNameSection.hidden = !recent.length;

    elements.namePickerList.replaceChildren();
    roster.forEach(function (name) {
      elements.namePickerList.appendChild(nameChoiceButton(name, false));
    });
    elements.namePickerEmpty.hidden = Boolean(roster.length || recent.length);

    function matchesName(name) {
      return !normalizedQuery || name.toLowerCase().indexOf(normalizedQuery) >= 0;
    }
  }

  function uniqueNames(names) {
    var seen = Object.create(null);
    return names.filter(function (name) {
      var cleanName = String(name || "").trim();
      if (!cleanName || seen[cleanName]) {
        return false;
      }
      seen[cleanName] = true;
      return true;
    });
  }

  function nameChoiceButton(name, isCurrent) {
    var button = make("button", "name-choice", name);
    button.type = "button";
    button.classList.toggle("is-current", isCurrent);
    button.addEventListener("click", function () {
      applyPickedName(name);
    });
    return button;
  }

  function applyPickedName(value) {
    var name = String(value || "").trim();
    var meeting = namePickerTarget ? getMeeting(namePickerTarget.meetingId) : null;
    var mapping = meeting ? meeting.mappings[namePickerTarget.mappingIndex] : null;
    if (!name || !mapping) {
      return;
    }
    var previousName = mapping.name;
    Object.assign(mapping, core.applyNameDecision(mapping, name));
    state.recentNames = uniqueNames([name, previousName].concat(state.recentNames)).slice(0, 12);
    refreshReviewedSnapshot(meeting);
    closeNamePicker();
    renderMappings();
    renderMeetingList();
    renderOutput();
    save();
    showToast(
      mapping.action === "replace" && mapping.confidence === "high"
        ? name + " · 智能替换 · 高置信"
        : name + " · 已恢复原建议"
    );
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
    var buttons = elements.mappingList.querySelectorAll(".mapping-name");
    if (buttons.length) {
      buttons[buttons.length - 1].click();
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

  var CONFIRM_ENDPOINT = "/api/confirm";

  async function submitConfirm() {
    if (!localSubmitEnabled) {
      showToast("确认回写仅在本地服务模式可用");
      return;
    }
    var text = elements.jsonOutput.value;
    var payload = null;
    try {
      payload = JSON.parse(text);
    } catch (error) {
      payload = null;
    }
    if (!payload || !Array.isArray(payload.batch) || !payload.batch.length) {
      showToast("还没有已确认的会议，先确认再回写");
      return;
    }
    var buttons = [byId("submitConfirmButton"), byId("submitQuickButton")];
    buttons.forEach(function (button) {
      button.disabled = true;
    });
    try {
      var response = await fetch(CONFIRM_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: text
      });
      var result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.error || "HTTP " + response.status);
      }
      showToast("已提交回写 " + payload.batch.length + " 场，本地处理程序将完成归档回写");
    } catch (error) {
      showToast("提交失败：本地处理程序未启动，可改用「复制」发回会话");
    } finally {
      buttons.forEach(function (button) {
        button.disabled = false;
      });
    }
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
    elements.outputPanel.setAttribute("aria-hidden", target === "output" ? "false" : "true");
    elements.outputToggleButton.setAttribute(
      "aria-expanded",
      target === "output" ? "true" : "false"
    );
  }

  function save() {
    if (forceDemo) {
      return;
    }
    var snapshot = {
      meetings: state.meetings,
      activeId: state.activeId,
      reviewed: state.reviewed,
      filter: state.filter,
      roster: state.roster,
      recentNames: state.recentNames,
      rosterVersion: state.rosterVersion,
      taskGeneratedAt: state.taskGeneratedAt
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
      state.recentNames = Array.isArray(snapshot.recentNames)
        ? core.parseRoster(snapshot.recentNames.join("\n")).slice(0, 12)
        : [];
      state.rosterVersion = snapshot.rosterVersion || "";
      state.taskGeneratedAt = snapshot.taskGeneratedAt || "";

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

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
