/**
 * Post-Edit-Modal: Gemeinsame Logik für Dashboard und Content Planner.
 * Öffnen, Befüllen, Speichern, Löschen; Custom Time-Picker (Dark Theme).
 * Kommentare auf Deutsch.
 */
(function () {
  function getApi() {
    return window.TrendDashPlanner;
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  /** Custom Time-Picker: dunkles Dropdown statt nativer weißer Browser-Picker */
  function initTimePicker() {
    var wrap = document.querySelector(".td-time-wrap");
    var input = getEl("postEditFieldTime");
    var pickerEl = getEl("postEditTimePicker");
    if (!wrap || !input || !pickerEl) return;

    var hours = [];
    var mins = ["00", "15", "30", "45"];
    for (var h = 0; h < 24; h++) hours.push(String(h).padStart(2, "0"));

    function parseTime(str) {
      if (!str || !/^\d{1,2}:?\d{0,2}$/.test(str.replace(/\s/g, ""))) return { h: 19, m: "15" };
      var parts = str.replace(/\s/g, "").split(":");
      var h = parseInt(parts[0], 10);
      var m = parts[1] != null ? parseInt(parts[1], 10) : 0;
      if (isNaN(h)) h = 19;
      if (isNaN(m)) m = 15;
      h = Math.max(0, Math.min(23, h));
      m = Math.max(0, Math.min(59, m));
      return { h: h, m: String(m).padStart(2, "0") };
    }

    function buildPicker() {
      var v = parseTime(input.value);
      var mDisplay = mins.indexOf(v.m) >= 0 ? v.m : "00";
      pickerEl.innerHTML =
        '<div class="td-time-picker-inner">' +
        '<div class="td-time-picker-col"><span class="td-time-picker-label">Std</span><div class="td-time-picker-list td-time-picker-hours"></div></div>' +
        '<div class="td-time-picker-col"><span class="td-time-picker-label">Min</span><div class="td-time-picker-list td-time-picker-mins"></div></div>' +
        "</div>";
      var hoursList = pickerEl.querySelector(".td-time-picker-hours");
      var minsList = pickerEl.querySelector(".td-time-picker-mins");
      hours.forEach(function (h) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "td-time-picker-option" + (parseInt(h, 10) === v.h ? " is-selected" : "");
        btn.textContent = h;
        btn.addEventListener("click", function () {
          pickerEl.querySelectorAll(".td-time-picker-hours .td-time-picker-option").forEach(function (b) { b.classList.remove("is-selected"); });
          btn.classList.add("is-selected");
          applyTime();
        });
        hoursList.appendChild(btn);
      });
      mins.forEach(function (m) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "td-time-picker-option" + (m === mDisplay ? " is-selected" : "");
        btn.textContent = m;
        btn.addEventListener("click", function () {
          pickerEl.querySelectorAll(".td-time-picker-mins .td-time-picker-option").forEach(function (b) { b.classList.remove("is-selected"); });
          btn.classList.add("is-selected");
          applyTime();
        });
        minsList.appendChild(btn);
      });
      minsList.scrollTop = minsList.querySelector(".is-selected") ? minsList.querySelector(".is-selected").offsetTop - 40 : 0;
      hoursList.scrollTop = hoursList.querySelector(".is-selected") ? hoursList.querySelector(".is-selected").offsetTop - 40 : 0;
    }

    function applyTime() {
      var hEl = pickerEl.querySelector(".td-time-picker-hours .is-selected");
      var mEl = pickerEl.querySelector(".td-time-picker-mins .is-selected");
      var h = hEl ? hEl.textContent.trim() : "19";
      var m = mEl ? mEl.textContent.trim() : "15";
      input.value = h + ":" + m;
    }

    input.addEventListener("focus", function () {
      pickerEl.setAttribute("aria-hidden", "false");
      pickerEl.classList.add("is-open");
      buildPicker();
    });

    input.addEventListener("click", function () {
      pickerEl.setAttribute("aria-hidden", "false");
      pickerEl.classList.add("is-open");
      buildPicker();
    });

    document.addEventListener("click", function (e) {
      if (pickerEl.classList.contains("is-open") && !wrap.contains(e.target)) {
        pickerEl.classList.remove("is-open");
        pickerEl.setAttribute("aria-hidden", "true");
      }
    });
  }

  /** Status-Select: farbige Badge-Klasse am Select setzen (für CSS) */
  function updateStatusSelectClass(selectEl) {
    if (!selectEl) return;
    selectEl.classList.remove("status-idea", "status-filming", "status-editing", "status-review", "status-ready");
    var v = (selectEl.value || "idea").toLowerCase();
    selectEl.classList.add("status-" + v);
  }

  function initPostEditModal() {
    var modal = getEl("postEditModal");
    var form = getEl("postEditForm");
    if (!modal || !form) return;

    var api = getApi();
    var currentPostId = null;

    var fieldTitle = getEl("postEditFieldTitle");
    var fieldDate = getEl("postEditFieldDate");
    var fieldTime = getEl("postEditFieldTime");
    var fieldStatus = getEl("postEditFieldStatus");
    var fieldNotes = getEl("postEditFieldNotes");
    var chkFilmed = getEl("postEditCheckFilmed");
    var chkEdited = getEl("postEditCheckEdited");
    var chkCaption = getEl("postEditCheckCaption");
    var chkSound = getEl("postEditCheckSound");
    var btnSave = getEl("postEditSave");
    var btnDelete = getEl("postEditDelete");

    function openModal(postId) {
      if (!api || typeof api.getPostById !== "function") return;
      var info = api.getPostById(postId);
      if (!info || !info.post) return;
      var post = info.post;
      currentPostId = post.id;

      fieldTitle.value = post.title || "";
      fieldDate.value = post.dateISO || "";
      fieldTime.value = post.time || "";
      fieldStatus.value = (post.status || "idea").toLowerCase();
      fieldNotes.value = post.notes || "";

      var checklist = post.checklist || {};
      chkFilmed.checked = !!checklist.filmed;
      chkEdited.checked = !!checklist.edited;
      chkCaption.checked = !!checklist.caption;
      chkSound.checked = !!checklist.sound;

      updateStatusSelectClass(fieldStatus);
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
      setTimeout(function () { fieldTitle.focus(); }, 50);
    }

    function closeModal() {
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      currentPostId = null;
      var picker = getEl("postEditTimePicker");
      if (picker) {
        picker.classList.remove("is-open");
        picker.setAttribute("aria-hidden", "true");
      }
    }

    fieldStatus.addEventListener("change", function () {
      updateStatusSelectClass(fieldStatus);
    });

    btnSave.addEventListener("click", function () {
      if (!currentPostId || !api || typeof api.upsertPost !== "function") return;
      var info = api.getPostById(currentPostId);
      if (!info || !info.post) return;

      var payload = {
        id: currentPostId,
        title: fieldTitle.value.trim() || info.post.title,
        dateISO: fieldDate.value || info.post.dateISO,
        time: fieldTime.value.trim() || info.post.time,
        platform: "IG",
        status: fieldStatus.value || "idea",
        notes: fieldNotes.value.trim() || "",
        checklist: {
          filmed: chkFilmed.checked,
          edited: chkEdited.checked,
          caption: chkCaption.checked,
          sound: chkSound.checked,
        },
      };
      api.upsertPost(payload);
      closeModal();
      window.dispatchEvent(new CustomEvent("trenddash-planner-updated"));
    });

    if (btnDelete) {
      btnDelete.addEventListener("click", function () {
        if (!currentPostId || !api || typeof api.deletePost !== "function") return;
        api.deletePost(currentPostId);
        closeModal();
        window.dispatchEvent(new CustomEvent("trenddash-planner-updated"));
      });
    }

    modal.querySelectorAll("[data-post-modal-close]").forEach(function (el) {
      el.addEventListener("click", closeModal);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal.classList.contains("is-open")) closeModal();
    });

    window.addEventListener("trenddash-open-post-modal", function (e) {
      var postId = e.detail && e.detail.postId;
      if (postId) openModal(postId);
    });

    initTimePicker();
  }

  document.addEventListener("DOMContentLoaded", initPostEditModal);
})();
