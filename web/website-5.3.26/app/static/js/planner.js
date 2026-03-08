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

  function toISODate(d) {
    return d.toISOString().slice(0, 10);
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

    return { postsByDate, nextId };
  }

  function loadState() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return createDefaultState();
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return createDefaultState();
      if (!parsed.postsByDate) parsed.postsByDate = {};
      if (!parsed.nextId) parsed.nextId = 1;
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

  function getPostById(id) {
    for (const [iso, list] of Object.entries(state.postsByDate)) {
      const index = list.findIndex((p) => p.id === id);
      if (index !== -1) {
        return { iso, index, post: list[index] };
      }
    }
    return null;
  }

  /** Alle Posts für To-Do-Engine: Montag dieser Woche bis heute + 30 Tage. Nutzt lokales Datum für konsistente Filterung. */
  function getPostsNext30Days() {
    const today = startOfDay(new Date());
    const monday = getMonday(today);
    const end = new Date(today);
    end.setDate(end.getDate() + 30);
    const startISO = toISODate(monday);
    const endISO = toISODate(end);
    const result = [];
    for (const [iso, list] of Object.entries(state.postsByDate)) {
      if (iso < startISO || iso > endISO) continue;
      for (const post of list) {
        result.push({ post: { ...post, checklist: cloneChecklist(post.checklist) }, dateISO: iso });
      }
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

  function platformIcon(platform) {
    const p = (platform || "").toLowerCase();
    if (p.includes("tt") || p.includes("tik")) return "TT";
    if (p.includes("yt") || p.includes("you")) return "YT";
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

          el.innerHTML = `
            <div class="planner-post-title">${post.title || "Neuer Post"}</div>
            <div class="planner-post-time">${post.time || "--:--"}</div>
            <div class="planner-post-meta">
              ${statusHtml}
              <span class="platform-badge" title="${post.platform || ""}">
                ${platformIcon(post.platform)}
              </span>
            </div>
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
        enableClicks: false,
        highlightToday: true,
        enableStatusEdit: isCurrentWeek,
        onStatusChange: isCurrentWeek
          ? function () {
              render();
              window.dispatchEvent(new CustomEvent("trenddash-planner-updated"));
            }
          : undefined,
        onPostClick: isCurrentWeek
          ? function (postId) {
              window.dispatchEvent(new CustomEvent("trenddash-open-post-modal", { detail: { postId } }));
            }
          : undefined,
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

  /* ---------- PLANNER PAGE (Post-Edit über gemeinsames Modal wie Dashboard) ---------- */
  function initPlannerPage() {
    const page = document.querySelector("[data-planner-page]");
    if (!page) return;

    const weekCard = page.querySelector('[data-week-context="planner"]');
    const labelEl = weekCard ? weekCard.querySelector("[data-week-label]") : null;
    const gridEl = weekCard ? weekCard.querySelector(".planner-week-grid") : null;
    const prevBtn = weekCard ? weekCard.querySelector('[data-week-nav="prev"]') : null;
    const nextBtn = weekCard ? weekCard.querySelector('[data-week-nav="next"]') : null;
    const platformFilterSelect = weekCard ? weekCard.querySelector("[data-week-filter]") : null;

    const pipelineIdea = page.querySelector('[data-pipeline-count="idea"]');
    const pipelineFilm = page.querySelector('[data-pipeline-count="filming"]');
    const pipelineEdit = page.querySelector('[data-pipeline-count="editing"]');
    const pipelineReview = page.querySelector('[data-pipeline-count="review"]');
    const pipelineReady = page.querySelector('[data-pipeline-count="ready"]');

    const gapButtons = Array.from(page.querySelectorAll("[data-gap-target]"));

    const btnNewPost = page.querySelector('[data-action="new-post"]');
    const btnAutoFill = page.querySelector('[data-action="autofill-week"]');
    const btnTemplate = page.querySelector('[data-action="template-post"]');

    let weekOffset = 0;
    let currentFilter = "all";

    function renderPipeline(stats) {
      if (pipelineIdea) pipelineIdea.textContent = stats.idea || 0;
      if (pipelineFilm) pipelineFilm.textContent = stats.filming || 0;
      if (pipelineEdit) pipelineEdit.textContent = stats.editing || 0;
      if (pipelineReview) pipelineReview.textContent = stats.review || 0;
      if (pipelineReady) pipelineReady.textContent = stats.ready || 0;
    }

    function applyFilter(week) {
      if (currentFilter === "all") return week;
      const allowed = currentFilter.toLowerCase();
      const filteredDays = week.days.map((day) => {
        const posts = day.posts.filter(
          (p) => platformIcon(p.platform).toLowerCase() === allowed
        );
        return { ...day, posts };
      });
      return { ...week, days: filteredDays };
    }

    function clearGapHighlights() {
      if (gridEl) {
        gridEl
          .querySelectorAll(".weekly-day--gap-target")
          .forEach((el) => el.classList.remove("weekly-day--gap-target"));
      }
    }

    function render() {
      if (!gridEl) return;
      let week = getWeekData(weekOffset);
      const totalPosts = week.days.reduce((s, d) => s + d.posts.length, 0);

      renderPipeline(week.stats);

      if (labelEl) {
        labelEl.textContent = `${week.label} · ${totalPosts} geplante Posts`;
      }

      week = applyFilter(week);

      renderWeekGrid(gridEl, week, {
        compact: false,
        enableClicks: true,
        highlightToday: true,
        onPostClick: (postId) => {
          window.dispatchEvent(new CustomEvent("trenddash-open-post-modal", { detail: { postId } }));
        },
      });
    }

    window.addEventListener("trenddash-planner-updated", render);

    btnNewPost &&
      btnNewPost.addEventListener("click", () => {
        const today = new Date();
        const monday = getMonday(new Date());
        const sunday = new Date(monday);
        sunday.setDate(sunday.getDate() + 6);

        let targetDate;
        if (today >= monday && today <= sunday) {
          targetDate = today;
        } else {
          targetDate = monday;
        }

        const iso = toISODate(targetDate);
        upsertPost({
          title: "Neuer Post",
          dateISO: iso,
          time: "18:00",
          platform: "IG",
          status: "idea",
          notes: "",
        });
        render();
      });

    btnAutoFill &&
      btnAutoFill.addEventListener("click", () => {
        const baseWeek = getWeekData(0);
        baseWeek.days.forEach((day) => {
          const list = state.postsByDate[day.dateISO] || [];
          if (list.length === 0) {
            upsertPost({
              title: `Auto-Post ${day.name}`,
              dateISO: day.dateISO,
              time: "19:00",
              platform: "TT",
              status: "idea",
              notes: "Automatisch vorgeschlagener Slot.",
            });
          }
        });
        render();
      });

    btnTemplate &&
      btnTemplate.addEventListener("click", () => {
        const todayISO = toISODate(new Date());
        upsertPost({
          title: "Template: 3 Gründe, warum Gäste wiederkommen",
          dateISO: todayISO,
          time: "17:00",
          platform: "IG",
          status: "idea",
        });
        render();
      });

    platformFilterSelect &&
      platformFilterSelect.addEventListener("change", () => {
        currentFilter = platformFilterSelect.value || "all";
        render();
      });

    // Gap-Highlight-Logik
    gapButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.dataset.gapTarget;
        clearGapHighlights();

        if (target === "friday") {
          const cols = gridEl.querySelectorAll('[data-weekday-index="4"]');
          cols.forEach((c) => c.classList.add("weekly-day--gap-target"));
        } else if (target === "empty") {
          gridEl.querySelectorAll(".weekly-day").forEach((col) => {
            const hasPost = col.querySelector(".planner-post");
            if (!hasPost) {
              col.classList.add("weekly-day--gap-target");
            }
          });
        } else {
          // andere Gaps markieren einfach nichts Spezifisches
        }
      });
    });

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

  document.addEventListener("DOMContentLoaded", () => {
    initDashboardPreview();
    initPlannerPage();
  });

  // API für Dashboard & Planner: To-Do-Engine (getPostsNext30Days), Post-Modal, deletePost
  window.TrendDashPlanner = { getWeekData, getPostsNext30Days, updatePostStatus, getPostById, upsertPost, deletePost };
})();
