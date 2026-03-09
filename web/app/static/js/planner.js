// static/js/planner.js
(function () {
  const STORAGE_KEY = "trenddash-planner-state-v1";

  const DEFAULT_CHECKLIST = {
    filmed: false,
    edited: false,
    caption: false,
    sound: false,
  };

  function cloneChecklist(c) {
    return { ...DEFAULT_CHECKLIST, ...(c || {}) };
  }

  function startOfDay(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    return x;
  }

  function sameDay(a, b) {
    return startOfDay(a).getTime() === startOfDay(b).getTime();
  }

  function getMonday(date) {
    const d = startOfDay(date);
    const day = (d.getDay() + 6) % 7; // 0 = Montag
    d.setDate(d.getDate() - day);
    return d;
  }

  /** Datum als YYYY-MM-DD in Lokalzeit (kein UTC), verhindert Off-by-One im Kalender. */
  function toISODate(d) {
    const x = new Date(d);
    const y = x.getFullYear();
    const m = String(x.getMonth() + 1).padStart(2, "0");
    const day = String(x.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  function getISOWeekNumber(date) {
    const d = new Date(
      Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
    );
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.floor(((d - yearStart) / 86400000 + 1) / 7);
  }

  function createDefaultState() {
    const postsByDate = {};
    let nextId = 1;
    const monday = getMonday(new Date());

    function add(offset, fields) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + offset);
      const iso = toISODate(d);
      if (!postsByDate[iso]) postsByDate[iso] = [];
      postsByDate[iso].push({
        id: String(nextId++),
        dateISO: iso,
        title: fields.title || "",
        time: fields.time || "",
        platform: fields.platform || "IG",
        status: fields.status || "ready",
        notes: fields.notes || "",
        checklist: cloneChecklist(fields.checklist),
      });
    }

    add(0, {
      title: "POV: First Bite – neues Menü",
      time: "18:00",
      platform: "IG",
      status: "ready",
    });
    add(1, {
      title: "Behind the Scenes: Teig & Ofen",
      time: "17:30",
      platform: "TT",
      status: "editing",
    });
    add(2, {
      title: "Trend-Reel: Cozy Restaurant Vibes",
      time: "20:00",
      platform: "IG",
      status: "filming",
    });
    add(3, {
      title: "Review: Neues Tiramisu Special",
      time: "19:15",
      platform: "YT",
      status: "idea",
    });
    add(5, {
      title: "POV: Samstagabend im Restaurant",
      time: "21:00",
      platform: "IG",
      status: "ready",
    });

    // Unscheduled Ideas (noch keinem Datum zugeordnet)
    const unscheduledIdeas = [
      { id: "unsched-1", title: "POV Kitchen Chaos", format: "Reel", status: "idea" },
      { id: "unsched-2", title: "Signature Dish Story", format: "Story", status: "idea" },
      { id: "unsched-3", title: "Guest Reaction", format: "Reel", status: "idea" },
    ];
    return { postsByDate, nextId, unscheduledIdeas };
  }

  function loadState() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return createDefaultState();
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return createDefaultState();
      if (!parsed.postsByDate) parsed.postsByDate = {};
      if (!parsed.nextId) parsed.nextId = 1;
      if (!Array.isArray(parsed.unscheduledIdeas)) parsed.unscheduledIdeas = [];
      return parsed;
    } catch (e) {
      console.warn("Planner: load failed", e);
      return createDefaultState();
    }
  }

  let state = loadState();

  function saveState() {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.warn("Planner: save failed", e);
    }
  }

  function computePipelineStats() {
    const stats = {
      idea: 0,
      filming: 0,
      editing: 0,
      review: 0,
      ready: 0,
      posted: 0,
    };
    Object.values(state.postsByDate).forEach((posts) => {
      posts.forEach((p) => {
        const key = (p.status || "").toLowerCase();
        if (stats.hasOwnProperty(key)) stats[key]++;
      });
    });
    return stats;
  }

  function getWeekData(weekOffset) {
    const baseMonday = getMonday(new Date());
    const monday = new Date(baseMonday);
    monday.setDate(monday.getDate() + weekOffset * 7);

    const today = startOfDay(new Date());
    const dayNames = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
    const days = [];

    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      const iso = toISODate(d);
      const dateLabel = d.toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
      });
      days.push({
        index: i,
        name: dayNames[i],
        dateISO: iso,
        dateLabel,
        isToday: sameDay(d, today),
        posts: (state.postsByDate[iso] || []).map((p) => ({
          ...p,
          checklist: cloneChecklist(p.checklist),
        })),
      });
    }

    const weekNum = getISOWeekNumber(monday);
    const weekRangeLabel = `${days[0].dateLabel} – ${days[6].dateLabel}`;

    return {
      weekOffset,
      label: `KW ${weekNum} · ${weekRangeLabel}`,
      days,
      stats: computePipelineStats(),
    };
  }

  /** Monatskalender: erstes Bild des Monats (monthOffset: 0 = aktueller Monat), 6 Wochen × 7 Tage. */
  function getMonthData(monthOffset) {
    const today = startOfDay(new Date());
    const first = new Date(today.getFullYear(), today.getMonth() + monthOffset, 1);
    const year = first.getFullYear();
    const month = first.getMonth();
    const dayNames = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
    const monthLabel = first.toLocaleDateString("de-DE", { month: "long", year: "numeric" });

    const firstDayOfMonth = new Date(year, month, 1);
    const dow = (firstDayOfMonth.getDay() + 6) % 7;
    const startMonday = new Date(firstDayOfMonth);
    startMonday.setDate(startMonday.getDate() - dow);

    const weeks = [];
    for (let w = 0; w < 6; w++) {
      const week = [];
      for (let d = 0; d < 7; d++) {
        const cellDate = new Date(startMonday);
        cellDate.setDate(startMonday.getDate() + w * 7 + d);
        const iso = toISODate(cellDate);
        const isCurrentMonth = cellDate.getMonth() === month;
        const posts = (state.postsByDate[iso] || []).map((p) => ({
          ...p,
          checklist: cloneChecklist(p.checklist),
        }));
        week.push({
          dateISO: iso,
          dayNum: cellDate.getDate(),
          isCurrentMonth,
          isToday: sameDay(cellDate, today),
          posts,
        });
      }
      weeks.push(week);
    }
    return { monthLabel, dayNames, weeks };
  }

  function getPostById(id) {
    for (const [iso, list] of Object.entries(state.postsByDate)) {
      const index = list.findIndex((p) => p.id === id);
      if (index !== -1) {
        return { iso, index, post: list[index] };
      }
    }
    return null;
  }

  /** Alle Posts für To-Do-Engine: Montag dieser Woche bis heute + 30 Tage.
   *  Filterung per lokalem Datum (Parsing iso + T12:00:00), damit Zeitzonen keine Lücken erzeugen. */
  function getPostsNext30Days() {
    const today = startOfDay(new Date());
    const monday = getMonday(today);
    const end = new Date(today);
    end.setDate(end.getDate() + 30);
    const result = [];
    for (const [iso, list] of Object.entries(state.postsByDate)) {
      const dayStart = startOfDay(new Date(iso + "T12:00:00"));
      if (dayStart < monday || dayStart > end) continue;
      for (const post of list) {
        result.push({ post: { ...post, checklist: cloneChecklist(post.checklist) }, dateISO: iso });
      }
    }
    if (typeof console !== "undefined" && console.log) {
      console.log("getPostsNext30Days() result:", result.length, "posts", result);
    }
    return result;
  }

  function upsertPost(updated) {
    if (!updated) return;

    // Update bestehend
    if (updated.id) {
      const info = getPostById(updated.id);
      if (info) {
        const oldIso = info.iso;
        const oldIdx = info.index;
        const oldPost = info.post;
        const newIso = updated.dateISO || oldIso;

        if (newIso !== oldIso) {
          state.postsByDate[oldIso].splice(oldIdx, 1);
          if (state.postsByDate[oldIso].length === 0) {
            delete state.postsByDate[oldIso];
          }
          if (!state.postsByDate[newIso]) state.postsByDate[newIso] = [];
          state.postsByDate[newIso].push({
            ...oldPost,
            ...updated,
            dateISO: newIso,
          });
        } else {
          state.postsByDate[oldIso][oldIdx] = {
            ...oldPost,
            ...updated,
            dateISO: newIso,
          };
        }
        saveState();
        return;
      }
    }

    // Neuer Post
    const iso = updated.dateISO;
    if (!iso) return;

    const id = String(state.nextId++);
    if (!state.postsByDate[iso]) state.postsByDate[iso] = [];
    state.postsByDate[iso].push({
      id,
      title: updated.title || "",
      time: updated.time || "",
      platform: updated.platform || "IG",
      status: updated.status || "idea",
      dateISO: iso,
      notes: updated.notes || "",
      checklist: cloneChecklist(updated.checklist),
    });
    saveState();
  }

  function deletePost(id) {
    const info = getPostById(id);
    if (!info) return;
    const { iso, index } = info;
    state.postsByDate[iso].splice(index, 1);
    if (state.postsByDate[iso].length === 0) {
      delete state.postsByDate[iso];
    }
    saveState();
  }

  /** Plattform-Badge: immer "IG" (Instagram) anzeigen – einheitliche Darstellung. */
  function platformIcon(platform) {
    return "IG";
  }

  function statusLabel(status) {
    switch ((status || "").toLowerCase()) {
      case "idea":
        return "Idee";
      case "filming":
        return "Filmen";
      case "editing":
        return "Editing";
      case "review":
        return "Review";
      case "ready":
        return "Ready";
      case "posted":
        return "Posted";
      default:
        return status || "Idee";
    }
  }

  /** Zyklus: Idee → Filmen → Editing → Review → Ready (für Inline-Edit im Dashboard) */
  const STATUS_CYCLE = ["idea", "filming", "editing", "review", "ready"];
  function getNextStatus(current) {
    const s = (current || "").toLowerCase();
    const idx = STATUS_CYCLE.indexOf(s);
    const next = idx === -1 ? 0 : (idx + 1) % STATUS_CYCLE.length;
    return STATUS_CYCLE[next];
  }

  /** Nur Status eines Posts aktualisieren (für Dashboard Inline-Edit). Speichert State. */
  function updatePostStatus(postId, newStatus) {
    const info = getPostById(postId);
    if (!info) return;
    const post = info.post;
    upsertPost({ ...post, status: newStatus });
    saveState();
    window.dispatchEvent(new CustomEvent("trenddash-planner-updated"));
  }

  /** Post auf neues Datum verschieben (Drag & Drop); Uhrzeit bleibt. */
  function updatePostDate(postId, newDateISO) {
    const info = getPostById(postId);
    if (!info || !newDateISO) return;
    const post = info.post;
    upsertPost({ ...post, dateISO: newDateISO });
    saveState();
    window.dispatchEvent(new CustomEvent("trenddash-planner-updated"));
  }

  function removeUnscheduledIdea(id) {
    if (!state.unscheduledIdeas) return;
    state.unscheduledIdeas = state.unscheduledIdeas.filter((i) => i.id !== id);
    saveState();
  }

  function getUnscheduledIdeas() {
    return state.unscheduledIdeas || [];
  }

  /** Titel für Anzeige kürzen: maximal maxWords Wörter, danach "…". */
  function truncateWords(str, maxWords) {
    if (str == null || String(str).trim() === "") return "Neuer Post";
    const s = String(str).trim();
    const words = s.split(/\s+/);
    if (words.length <= maxWords) return s;
    return words.slice(0, maxWords).join(" ") + "…";
  }

  function renderWeekGrid(container, week, options) {
    if (!container || !week) return;
    const opts = options || {};
    const compact = !!opts.compact;
    const enableClicks = !!opts.enableClicks;
    const onPostClick = opts.onPostClick;
    const highlightToday = !!opts.highlightToday;
    const enableStatusEdit = !!opts.enableStatusEdit;
    const onStatusChange = opts.onStatusChange;

    container.innerHTML = "";

    week.days.forEach((day) => {
      const col = document.createElement("div");
      col.className = "weekly-day";
      col.dataset.weekdayIndex = String(day.index);
      col.dataset.dateIso = day.dateISO;

      if (highlightToday && day.isToday && week.weekOffset === 0) {
        col.classList.add("weekly-day--today");
      }

      col.innerHTML = `
        <div class="weekly-day-header">
          <span class="weekly-day-name">${day.name}</span>
          <span class="weekly-day-date">${day.dateLabel}</span>
        </div>
        <div class="weekly-day-posts"></div>
      `;

      const postsContainer = col.querySelector(".weekly-day-posts");

      if (opts.enableUnscheduledDrop && typeof opts.onUnscheduledDrop === "function") {
        col.addEventListener("dragover", (e) => {
          if (!e.dataTransfer.types.includes("application/trenddash-unscheduled")) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
          col.classList.add("weekly-day--drop-over");
        });
        col.addEventListener("dragleave", () => col.classList.remove("weekly-day--drop-over"));
        col.addEventListener("drop", (e) => {
          if (!e.dataTransfer.types.includes("application/trenddash-unscheduled")) return;
          e.preventDefault();
          col.classList.remove("weekly-day--drop-over");
          const ideaId = e.dataTransfer.getData("application/trenddash-unscheduled");
          if (ideaId && day.dateISO) opts.onUnscheduledDrop(ideaId, day.dateISO);
        });
      }

      if (!day.posts.length) {
        postsContainer.innerHTML =
          '<div class="weekly-empty">Keine Posts geplant</div>';
      } else {
        day.posts.forEach((post) => {
          const el = document.createElement(enableClicks && !enableStatusEdit ? "button" : "div");
          if (enableClicks && !enableStatusEdit) el.type = "button";
          el.className =
            "planner-post" + (compact ? " planner-post--compact" : "");
          el.dataset.postId = post.id;
          el.dataset.dateIso = day.dateISO;

          const statusClass = (post.status || "").toLowerCase();
          const statusHtml = enableStatusEdit
            ? `<button type="button" class="status-badge status-badge--clickable status-inline status-${statusClass}" data-status-cycle aria-label="Status ändern">
                <span class="status-dot" aria-hidden="true"></span>
                <span class="status-text">${statusLabel(post.status)}</span>
              </button>`
            : `<span class="status-inline status-${statusClass}">
                <span class="status-dot" aria-hidden="true"></span>
                <span class="status-text">${statusLabel(post.status)}</span>
              </span>`;

          const titleDisplay = truncateWords(post.title, 3);
          el.innerHTML = `
            <div class="planner-post-title">${escapeHtml(titleDisplay)}</div>
            <div class="planner-post-time">${post.time || "--:--"}</div>
            <div class="planner-post-meta">
              ${statusHtml}
            </div>
            <span class="platform-badge platform-badge--card" title="Instagram">IG</span>
          `;

          if (enableStatusEdit) {
            const statusBtn = el.querySelector("[data-status-cycle]");
            if (statusBtn && typeof onStatusChange === "function") {
              statusBtn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                const next = getNextStatus(post.status);
                if (window.TrendDashPlanner && typeof window.TrendDashPlanner.updatePostStatus === "function") {
                  window.TrendDashPlanner.updatePostStatus(post.id, next);
                }
                onStatusChange(post.id);
              });
            }
            // Klick auf Karte (nicht auf Status-Badge) öffnet Post-Edit-Modal
            const onPostClickOpt = opts.onPostClick;
            if (typeof onPostClickOpt === "function") {
              el.addEventListener("click", (e) => {
                if (e.target.closest("[data-status-cycle]")) return;
                onPostClickOpt(post.id);
              });
              el.style.cursor = "pointer";
            }
          } else if (enableClicks && typeof onPostClick === "function") {
            el.addEventListener("click", () => onPostClick(post.id));
          }

          postsContainer.appendChild(el);
        });
      }

      container.appendChild(col);
    });
  }

  /** Status-Farbe für Kalender-Post-Dot: idea=grau, filming=blau, editing=violett, review=orange, ready=grün */
  function statusDotClass(status) {
    const s = (status || "").toLowerCase();
    if (s === "idea") return "planner-post-dot--idea";
    if (s === "filming") return "planner-post-dot--filming";
    if (s === "editing") return "planner-post-dot--editing";
    if (s === "review") return "planner-post-dot--review";
    if (s === "ready") return "planner-post-dot--ready";
    return "planner-post-dot--idea";
  }

  function renderMonthGrid(container, monthData, options) {
    if (!container || !monthData) return;
    const onPostClick = options && options.onPostClick;
    container.innerHTML = "";

    const headerRow = document.createElement("div");
    headerRow.className = "planner-month-row planner-month-row--head";
    monthData.dayNames.forEach((name) => {
      const th = document.createElement("div");
      th.className = "planner-month-cell planner-month-cell--head";
      th.textContent = name;
      headerRow.appendChild(th);
    });
    container.appendChild(headerRow);

    monthData.weeks.forEach((week) => {
      const row = document.createElement("div");
      row.className = "planner-month-row";
      week.forEach((cell) => {
        const cellEl = document.createElement("div");
        cellEl.className = "planner-month-cell";
        cellEl.dataset.dateIso = cell.dateISO;
        cellEl.setAttribute("data-drop-target", "day");
        if (!cell.isCurrentMonth) cellEl.classList.add("planner-month-cell--other-month");
        if (cell.isToday) cellEl.classList.add("planner-month-cell--today");

        const dayNum = document.createElement("div");
        dayNum.className = "planner-month-day-num";
        dayNum.textContent = cell.dayNum;
        cellEl.appendChild(dayNum);

        const postsWrap = document.createElement("div");
        postsWrap.className = "planner-month-posts";
        const maxPostsVisible = 2;
        const postsToShow = cell.posts.slice(0, maxPostsVisible);
        const moreCount = cell.posts.length - maxPostsVisible;

        postsToShow.forEach((post) => {
          const card = document.createElement("div");
          card.className = "planner-month-post";
          card.draggable = true;
          card.dataset.postId = post.id;
          card.dataset.dateIso = cell.dateISO;
          card.setAttribute("data-draggable", "post");
          const dotClass = statusDotClass(post.status);
          const titleDisplay = truncateWords(post.title, 2);
          card.innerHTML =
            '<span class="planner-post-dot ' +
            dotClass +
            '" aria-hidden="true"></span>' +
            '<div class="planner-month-post-inner">' +
            '<span class="planner-month-post-title">' +
            escapeHtml(titleDisplay) +
            "</span>" +
            '<span class="planner-month-post-time">' +
            (post.time || "--:--") +
            "</span>" +
            "</div>" +
            '<span class="planner-month-post-badge" title="Instagram">IG</span>';
          card.addEventListener("click", (e) => {
            e.stopPropagation();
            if (onPostClick && typeof onPostClick === "function") onPostClick(post.id);
          });
          card.addEventListener("dragstart", (e) => {
            e.dataTransfer.setData("application/trenddash-post", post.id);
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", post.id);
            card.classList.add("planner-post-dragging");
          });
          card.addEventListener("dragend", () => card.classList.remove("planner-post-dragging"));
          postsWrap.appendChild(card);
        });
        if (moreCount > 0) {
          const moreEl = document.createElement("div");
          moreEl.className = "planner-month-more";
          moreEl.textContent = "+" + moreCount + " mehr";
          postsWrap.appendChild(moreEl);
        }

        cellEl.appendChild(postsWrap);

        cellEl.addEventListener("dragover", (e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          cellEl.classList.add("planner-month-cell--drop-over");
        });
        cellEl.addEventListener("dragleave", () => cellEl.classList.remove("planner-month-cell--drop-over"));
        cellEl.addEventListener("drop", (e) => {
          e.preventDefault();
          cellEl.classList.remove("planner-month-cell--drop-over");
          const postId = e.dataTransfer.getData("application/trenddash-post") || e.dataTransfer.getData("text/plain");
          const ideaId = e.dataTransfer.getData("application/trenddash-unscheduled");
          if (postId && window.TrendDashPlanner && typeof window.TrendDashPlanner.updatePostDate === "function") {
            window.TrendDashPlanner.updatePostDate(postId, cell.dateISO);
          }
          if (ideaId && cell.dateISO) {
            const idea = (state.unscheduledIdeas || []).find((i) => i.id === ideaId);
            if (idea) {
              upsertPost({
                title: idea.title,
                dateISO: cell.dateISO,
                time: "18:00",
                platform: "IG",
                status: "idea",
                notes: "",
              });
              removeUnscheduledIdea(ideaId);
              if (typeof options.onUnscheduledScheduled === "function") options.onUnscheduledScheduled();
            }
          }
        });

        row.appendChild(cellEl);
      });
      container.appendChild(row);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : str;
    return div.innerHTML;
  }

  /* ---------- DASHBOARD PREVIEW (mit Inline-Status-Edit) ---------- */
  function initDashboardPreview() {
    const card = document.querySelector('[data-week-context="dashboard"]');
    if (!card) return;

    const labelEl = card.querySelector("[data-week-label]");
    const gridEl = card.querySelector(".weekly-grid");
    const prevBtn = card.querySelector('[data-week-nav="prev"]');
    const nextBtn = card.querySelector('[data-week-nav="next"]');

    let weekOffset = 0;

    function render() {
      const week = getWeekData(weekOffset);
      const totalPosts = week.days.reduce((s, d) => s + d.posts.length, 0);

      if (labelEl) {
        labelEl.textContent = `${week.label} · ${totalPosts} geplante Posts`;
      }

      const isCurrentWeek = weekOffset === 0;
      renderWeekGrid(gridEl, week, {
        compact: true,
        enableClicks: true,
        highlightToday: true,
        enableStatusEdit: true,
        onStatusChange: function () {
          render();
        },
        onPostClick: function (postId) {
          window.dispatchEvent(new CustomEvent("trenddash-open-post-modal", { detail: { postId } }));
        },
      });
    }

    window.addEventListener("trenddash-planner-updated", render);

    prevBtn &&
      prevBtn.addEventListener("click", () => {
        weekOffset--;
        render();
      });
    nextBtn &&
      nextBtn.addEventListener("click", () => {
        weekOffset++;
        render();
      });

    render();
  }

  /* ---------- PLANNER PAGE WEEK: Wochenplan + Unscheduled + Content Gaps ---------- */
  function initPlannerPageWeek() {
    const page = document.querySelector('[data-planner-page][data-planner-view="week"]');
    if (!page) return;

    const labelEl = page.querySelector("[data-week-label]");
    const gridEl = page.querySelector("[data-planner-week-grid]");
    const prevBtn = page.querySelector('[data-week-nav="prev"]');
    const nextBtn = page.querySelector('[data-week-nav="next"]');
    const unscheduledListEl = page.querySelector("[data-unscheduled-list]");
    const unscheduledShowAllBtn = document.getElementById("plannerUnscheduledShowAll");
    const scheduleModal = document.getElementById("plannerScheduleIdeaModal");
    const scheduleDateEl = document.getElementById("plannerScheduleDate");
    const scheduleTimeEl = document.getElementById("plannerScheduleTime");
    const scheduleSubmitBtn = document.getElementById("plannerScheduleIdeaSubmit");

    let weekOffset = 0;
    let selectedUnscheduledId = null;
    let showAllUnscheduled = false;

    function setScheduleModalDateToday() {
      const d = new Date();
      if (scheduleDateEl) scheduleDateEl.value = d.toISOString().slice(0, 10);
    }
    function openScheduleIdeaModal(ideaId) {
      selectedUnscheduledId = ideaId;
      setScheduleModalDateToday();
      if (scheduleTimeEl) scheduleTimeEl.value = "18:00";
      if (scheduleModal) {
        scheduleModal.classList.add("is-open");
        scheduleModal.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
      }
    }
    function closeScheduleIdeaModal() {
      selectedUnscheduledId = null;
      if (scheduleModal) {
        scheduleModal.classList.remove("is-open");
        scheduleModal.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
      }
    }

    function renderWeek() {
      const week = getWeekData(weekOffset);
      const totalPosts = week.days.reduce((s, d) => s + d.posts.length, 0);
      if (labelEl) labelEl.textContent = week.label + " · " + totalPosts + " geplante Posts";
      if (gridEl) {
        renderWeekGrid(gridEl, week, {
          compact: true,
          enableClicks: true,
          highlightToday: true,
          enableStatusEdit: true,
          enableUnscheduledDrop: true,
          onStatusChange: () => { renderWeek(); },
          onPostClick: (postId) => {
            window.dispatchEvent(new CustomEvent("trenddash-open-post-modal", { detail: { postId } }));
          },
          onUnscheduledDrop: (ideaId, dateISO) => {
            const idea = (state.unscheduledIdeas || []).find((i) => i.id === ideaId);
            if (idea) {
              upsertPost({
                title: idea.title,
                dateISO: dateISO,
                time: "18:00",
                platform: "IG",
                status: "idea",
                notes: "",
              });
              removeUnscheduledIdea(ideaId);
            }
            render();
          },
        });
      }
    }

    function renderUnscheduled() {
      if (!unscheduledListEl) return;
      const ideas = getUnscheduledIdeas();
      const maxShow = showAllUnscheduled ? ideas.length : 5;
      const toShow = ideas.slice(0, maxShow);
      unscheduledListEl.innerHTML = "";
      if (ideas.length === 0) {
        unscheduledListEl.innerHTML = '<p class="planner-unscheduled-empty">Keine ungeplanten Ideen.</p>';
        if (unscheduledShowAllBtn) unscheduledShowAllBtn.hidden = true;
        return;
      }
      toShow.forEach((idea) => {
        const block = document.createElement("button");
        block.type = "button";
        block.className = "ai-idea-block";
        block.dataset.ideaId = idea.id;
        block.draggable = true;
        block.setAttribute("data-draggable", "unscheduled");
        block.innerHTML =
          '<div class="ai-idea-block-header">' +
          '<h4 class="ai-idea-block-title">' + escapeHtml(idea.title) + "</h4>" +
          (idea.format ? '<span class="ai-idea-block-tag">' + escapeHtml(idea.format) + "</span>" : "") +
          "</div>" +
          '<p class="ai-idea-block-preview">Idee</p>';
        block.addEventListener("click", () => openScheduleIdeaModal(idea.id));
        block.addEventListener("dragstart", (e) => {
          e.dataTransfer.setData("application/trenddash-unscheduled", idea.id);
          e.dataTransfer.effectAllowed = "copy";
        });
        unscheduledListEl.appendChild(block);
      });
      if (unscheduledShowAllBtn) {
        unscheduledShowAllBtn.hidden = ideas.length <= 5;
        unscheduledShowAllBtn.textContent = showAllUnscheduled ? "Weniger anzeigen" : "Alle Ideen anzeigen";
      }
    }

    function render() {
      renderWeek();
      renderUnscheduled();
    }

    window.addEventListener("trenddash-planner-updated", render);
    if (prevBtn) prevBtn.addEventListener("click", () => { weekOffset--; render(); });
    if (nextBtn) nextBtn.addEventListener("click", () => { weekOffset++; render(); });

    if (scheduleSubmitBtn && scheduleDateEl && scheduleTimeEl) {
      scheduleSubmitBtn.addEventListener("click", () => {
        const dateVal = scheduleDateEl.value;
        const timeVal = scheduleTimeEl.value || "18:00";
        if (!dateVal || !selectedUnscheduledId) return;
        const idea = (state.unscheduledIdeas || []).find((i) => i.id === selectedUnscheduledId);
        if (idea) {
          upsertPost({
            title: idea.title,
            dateISO: dateVal,
            time: timeVal,
            platform: "IG",
            status: "idea",
            notes: "",
          });
          removeUnscheduledIdea(selectedUnscheduledId);
        }
        closeScheduleIdeaModal();
        render();
      });
    }
    if (scheduleModal) {
      scheduleModal.querySelectorAll("[data-schedule-idea-close]").forEach((el) => {
        el.addEventListener("click", closeScheduleIdeaModal);
      });
    }
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && scheduleModal && scheduleModal.classList.contains("is-open")) {
        closeScheduleIdeaModal();
      }
    });
    if (unscheduledShowAllBtn) {
      unscheduledShowAllBtn.addEventListener("click", () => {
        showAllUnscheduled = !showAllUnscheduled;
        renderUnscheduled();
      });
    }

    render();
  }

  /* ---------- PLANNER PAGE MONTH: nur Monatskalender ---------- */
  function initPlannerPageMonth() {
    const page = document.querySelector('[data-planner-page][data-planner-view="month"]');
    if (!page) return;

    const monthLabelEl = page.querySelector("[data-month-label]");
    const monthGridEl = page.querySelector("[data-month-grid]");
    const monthPrevBtn = page.querySelector('[data-month-nav="prev"]');
    const monthNextBtn = page.querySelector('[data-month-nav="next"]');

    let monthOffset = 0;

    function renderMonth() {
      const monthData = getMonthData(monthOffset);
      if (monthLabelEl) monthLabelEl.textContent = monthData.monthLabel;
      if (monthGridEl) {
        renderMonthGrid(monthGridEl, monthData, {
          onPostClick: (postId) => {
            window.dispatchEvent(new CustomEvent("trenddash-open-post-modal", { detail: { postId } }));
          },
        });
      }
    }

    window.addEventListener("trenddash-planner-updated", renderMonth);
    if (monthPrevBtn) monthPrevBtn.addEventListener("click", () => { monthOffset--; renderMonth(); });
    if (monthNextBtn) monthNextBtn.addEventListener("click", () => { monthOffset++; renderMonth(); });
    renderMonth();
  }

  document.addEventListener("DOMContentLoaded", () => {
    initDashboardPreview();
    const page = document.querySelector("[data-planner-page]");
    if (page) {
      const view = page.getAttribute("data-planner-view");
      if (view === "week") initPlannerPageWeek();
      else if (view === "month") initPlannerPageMonth();
    }
  });

  // API für Dashboard & Planner: To-Do-Engine, Post-Modal, Monatskalender, Unscheduled
  window.TrendDashPlanner = {
    getWeekData,
    getMonthData,
    getPostsNext30Days,
    updatePostStatus,
    updatePostDate,
    getPostById,
    upsertPost,
    deletePost,
    getUnscheduledIdeas,
  };
})();
