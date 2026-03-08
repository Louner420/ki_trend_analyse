/**
 * TrendDash – To-Do-Engine (nächste 30 Tage).
 * Datenquelle: getPostsNext30Days() für Dashboard und Overlay.
 * Sortierung: Überfällig → Heute → Morgen → Produktion → Planung.
 * Deadline-Anzeige: Überfällig / Heute / Morgen / In X Tagen.
 * Vanilla JS, Kommentare auf Deutsch.
 */
(function () {
  const VIDEOS_PER_WEEK = 3;
  const DASHBOARD_SHOW_COUNT = 5;

  function startOfDay(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    return x;
  }

  function getMonday(date) {
    const d = startOfDay(date);
    const day = (d.getDay() + 6) % 7;
    d.setDate(d.getDate() - day);
    return d;
  }

  /**
   * Generiert alle To-Dos aus den geplanten Posts.
   * Regeln:
   * - Upload - 3 Tage & Status "Idee" → Filmen fehlt
   * - Upload - 2 Tage & Status "Filmen" → Editing fehlt (muss geschnitten werden)
   * - Upload - 1 Tag & Status "Editing" → Review fehlt (muss überprüft werden)
   * - Upload-Tag & Status nicht "Ready" → Nicht Ready
   * - Pro Woche < 3 Videos → "Diese Woche fehlen noch X Videos"
   * @param {Array<{post: object, dateISO: string}>} posts - Von getPostsNext30Days()
   */
  function computeTodos(posts) {
    if (!posts || !Array.isArray(posts)) return [];
    const today = startOfDay(new Date());
    const todos = [];
    const seenPostKeys = new Set();

    function daysUntilUpload(iso) {
      const d = new Date(iso + "T12:00:00");
      return Math.ceil((startOfDay(d) - today) / 86400000);
    }

    // Video-To-Dos (auch überfällige: daysUntil < 0)
    for (const { post, dateISO } of posts) {
      const status = (post.status || "").toLowerCase();
      if (status === "posted") continue;
      const daysUntil = daysUntilUpload(dateISO);
      const title = post.title || "Ohne Titel";
      const dateLabel = new Date(dateISO + "T12:00:00").toLocaleDateString("de-DE", {
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
      });

      let added = false;
      // Upload-Tag oder überfällig & nicht Ready
      if (daysUntil <= 0 && status !== "ready") {
        seenPostKeys.add("post-" + post.id + "-not-ready");
        todos.push({
          key: "post-" + post.id + "-not-ready",
          type: "not-ready",
          postId: post.id,
          priorityLevel: daysUntil < 0 ? "red" : "red",
          sortOrder: 0,
          daysUntil,
          deadline: dateISO,
          text: "Video „" + title + "“ ist noch nicht bereit zum Posten.",
          hint: "Upload " + (daysUntil < 0 ? "überfällig " : "heute ") + dateLabel + ".",
          explanation: "Das Video sollte auf „Ready“ stehen.",
          context: "Upload " + (daysUntil < 0 ? "überfällig" : "heute") + ".",
          action: "Status auf „Ready“ setzen oder Post verschieben.",
          buttons: ["open-video"],
        });
        added = true;
      }
      if (!added && daysUntil <= 1 && status === "editing") {
        seenPostKeys.add("post-" + post.id + "-review");
        todos.push({
          key: "post-" + post.id + "-review",
          type: "must-review",
          postId: post.id,
          priorityLevel: daysUntil <= 0 ? "red" : daysUntil === 1 ? "yellow" : "blue",
          sortOrder: 3,
          daysUntil,
          deadline: dateISO,
          text: "Video „" + title + "“ muss noch überprüft werden.",
          hint: "Upload " + dateLabel + ".",
          explanation: "Ein Tag vor Upload sollte das Video im Review sein.",
          context: "Upload " + dateLabel + ".",
          action: "Letzte Prüfung und Status auf „Review“ bzw. „Ready“ setzen.",
          buttons: ["open-video"],
        });
        added = true;
      }
      if (!added && daysUntil <= 2 && status === "filming") {
        seenPostKeys.add("post-" + post.id + "-schnitt");
        todos.push({
          key: "post-" + post.id + "-schnitt",
          type: "must-edit",
          postId: post.id,
          priorityLevel: daysUntil <= 0 ? "red" : daysUntil <= 1 ? "yellow" : "blue",
          sortOrder: 2,
          daysUntil,
          deadline: dateISO,
          text: "Video „" + title + "“ muss noch geschnitten werden.",
          hint: "Upload " + dateLabel + ".",
          explanation: "2 Tage vor Upload sollte der Schnitt laufen.",
          context: "Upload am " + dateLabel + ".",
          action: "Video schneiden und Status auf „Editing“ setzen.",
          buttons: ["open-video"],
        });
        added = true;
      }
      if (!added && daysUntil <= 3 && status === "idea") {
        seenPostKeys.add("post-" + post.id + "-filmen");
        todos.push({
          key: "post-" + post.id + "-filmen",
          type: "must-film",
          postId: post.id,
          priorityLevel: daysUntil <= 0 ? "red" : daysUntil <= 1 ? "yellow" : "blue",
          sortOrder: 1,
          daysUntil,
          deadline: dateISO,
          text: "Video „" + title + "“ muss noch gefilmt werden.",
          hint: "Upload " + dateLabel + ".",
          explanation: "3 Tage vor Upload sollte das Video in Produktion sein.",
          context: "Upload am " + dateLabel + ".",
          action: "Video filmen und Status auf „Filmen“ setzen.",
          buttons: ["open-video"],
        });
        added = true;
      }
      if (!added && daysUntil <= 14 && daysUntil >= 0 && status !== "ready") {
        seenPostKeys.add("post-" + post.id + "-offen");
        todos.push({
          key: "post-" + post.id + "-offen",
          type: "not-ready",
          postId: post.id,
          priorityLevel: daysUntil <= 1 ? "red" : daysUntil <= 3 ? "yellow" : "blue",
          sortOrder: 5,
          daysUntil,
          deadline: dateISO,
          text: "Video „" + title + "“ noch nicht bereit (Status: " + (status === "idea" ? "Idee" : status === "filming" ? "Filmen" : status === "editing" ? "Editing" : status === "review" ? "Review" : status) + ").",
          hint: "Upload " + dateLabel + ".",
          explanation: "Das Video sollte rechtzeitig vor dem Upload durch die Pipeline.",
          context: "Upload am " + dateLabel + ".",
          action: "Status im Content Planner anpassen.",
          buttons: ["open-video"],
        });
      }
    }

    // Planungs-To-Dos: pro Woche mindestens 3 Videos
    const weekStart = getMonday(today);
    for (let w = 0; w < 5; w++) {
      const weekMonday = new Date(weekStart);
      weekMonday.setDate(weekStart.getDate() + w * 7);
      const weekSunday = new Date(weekMonday);
      weekSunday.setDate(weekMonday.getDate() + 6);
      const weekEndISO = weekSunday.toISOString().slice(0, 10);
      const weekStartISO = weekMonday.toISOString().slice(0, 10);
      let count = 0;
      for (const { dateISO } of posts) {
        if (dateISO >= weekStartISO && dateISO <= weekEndISO) count++;
      }
      if (count < VIDEOS_PER_WEEK && weekMonday.getTime() >= today.getTime() - 86400000 * 7) {
        const missing = VIDEOS_PER_WEEK - count;
        const key = "weekly-" + weekStartISO;
        if (!seenPostKeys.has(key)) {
          seenPostKeys.add(key);
          const rangeLabel =
            weekMonday.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) +
            " – " +
            weekSunday.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
          todos.push({
            key,
            type: "weekly-goal",
            priorityLevel: "blue",
            sortOrder: 10,
            daysUntil: null,
            deadline: null,
            weekStartISO,
            text: "Diese Woche fehlen noch " + missing + " Video(s).",
            hint: "Woche " + rangeLabel + ".",
            explanation: "Mindestens " + VIDEOS_PER_WEEK + " Videos pro Woche einplanen.",
            context: "Aktuell " + count + " von " + VIDEOS_PER_WEEK + " geplant.",
            action: "Weitere Videos einplanen oder AI-Videoideen nutzen.",
            buttons: ["ai-ideas"],
          });
        }
      }
    }

    // Sortierung: 1) Überfällig, 2) Heute, 3) Morgen, 4) Produktionsstatus, 5) Planung
    todos.sort((a, b) => {
      const da = a.daysUntil == null ? 999 : a.daysUntil;
      const db = b.daysUntil == null ? 999 : b.daysUntil;
      if (da !== db) return da - db;
      const pOrder = { red: 0, yellow: 1, blue: 2 };
      const pa = pOrder[a.priorityLevel] ?? 2;
      const pb = pOrder[b.priorityLevel] ?? 2;
      if (pa !== pb) return pa - pb;
      return (a.sortOrder ?? 5) - (b.sortOrder ?? 5);
    });
    return todos;
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function priorityClass(level) {
    if (level === "red") return "todo-priority--red";
    if (level === "yellow") return "todo-priority--yellow";
    return "todo-priority--blue";
  }

  /** Deadline-Label für Anzeige: Überfällig / Heute / Morgen / In X Tagen */
  function getDeadlineLabel(todo) {
    if (todo.deadline == null) return "";
    if (todo.daysUntil == null) return "";
    if (todo.daysUntil < 0) return "Überfällig";
    if (todo.daysUntil === 0) return "Heute";
    if (todo.daysUntil === 1) return "Morgen";
    return "In " + todo.daysUntil + " Tagen";
  }

  /** Priorität für Anzeige: Überfällig/Heute = rot, Morgen = gelb, 2+ = blau */
  function getPriorityLevel(todo) {
    if (todo.daysUntil != null && todo.daysUntil <= 0) return "red";
    if (todo.daysUntil === 1) return "yellow";
    return todo.priorityLevel || "blue";
  }

  function renderTodoList(container, list, dismissedKeys, options) {
    if (!container) return;
    const openTodoModal = options.openTodoModal;
    const onDismiss = options.onDismiss;
    const filtered = list.filter((t) => !dismissedKeys.has(t.key));
    container.innerHTML = "";
    filtered.forEach((todo) => {
      const wrap = document.createElement("div");
      wrap.className = "todo-item-wrap todo-item--enter";
      wrap.dataset.todoKey = todo.key;
      const deadlineLabel = getDeadlineLabel(todo);
      const level = getPriorityLevel(todo);
      const deadlineHtml =
        deadlineLabel === ""
          ? ""
          : '<span class="todo-deadline">Deadline: ' + escapeHtml(deadlineLabel) + "</span>";
      wrap.innerHTML =
        '<div class="todo-item ' +
        priorityClass(level) +
        '" role="button" tabindex="0" data-todo-key="' +
        todo.key +
        '">' +
        '<div class="todo-item-inner">' +
        '<span class="todo-check-wrap"><input type="checkbox" class="todo-check" aria-label="Als erledigt markieren" /></span>' +
        '<span class="todo-text">' +
        '<span class="todo-main">' +
        escapeHtml(todo.text) +
        "</span>" +
        (todo.hint ? '<span class="todo-hint">' + escapeHtml(todo.hint) + "</span>" : "") +
        deadlineHtml +
        "</span>" +
        "</div>" +
        "</div>";
      const itemEl = wrap.querySelector(".todo-item");
      const checkEl = wrap.querySelector(".todo-check");
      itemEl.addEventListener("click", (e) => {
        if (e.target === checkEl || e.target.closest(".todo-check-wrap")) return;
        e.preventDefault();
        openTodoModal(todo);
      });
      itemEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (e.target !== checkEl) openTodoModal(todo);
        }
      });
      checkEl.addEventListener("click", (e) => e.stopPropagation());
      checkEl.addEventListener("change", () => {
        dismissedKeys.add(todo.key);
        onDismiss(wrap);
      });
      container.appendChild(wrap);
    });
  }

  function animateOutAndRemove(wrap, callback) {
    if (!wrap) {
      if (callback) callback();
      return;
    }
    wrap.classList.add("todo-item--leaving");
    wrap.addEventListener(
      "transitionend",
      () => {
        wrap.remove();
        if (callback) callback();
      },
      { once: true }
    );
  }

  function init() {
    const wrapper = document.querySelector(".todo-list-wrapper");
    const emptyEl = document.querySelector(".dash-todos-card .todo-empty");
    const showAllBtn = document.getElementById("todoShowAllBtn");
    const todoDetailModal = document.getElementById("todoDetailModal");
    const todoOverlay = document.getElementById("todoAllOverlay");
    const todoOverlayList = document.getElementById("todoAllOverlayList");
    const todoOverlayClose = document.querySelector("[data-todo-overlay-close]");

    const dismissedKeys = new Set();
    const getPostsNext30Days =
      window.TrendDashPlanner && window.TrendDashPlanner.getPostsNext30Days;
    if (typeof getPostsNext30Days !== "function") {
      if (emptyEl) {
        emptyEl.hidden = false;
        emptyEl.textContent = "Wochenplan-Daten nicht geladen.";
      }
      return;
    }

    /**
     * Dashboard: getPostsNext30Days() → computeTodos → sortiert.
     * Rückgabe: komplette Liste (Anzeige auf 5 wird in doRender begrenzt).
     */
    function getTodoListDashboard() {
      const posts = getPostsNext30Days();
      console.log("posts for todo", posts);
      return computeTodos(posts);
    }

    /**
     * Overlay "Alle Aufgaben anzeigen": getPostsNext30Days() → computeTodos → komplette Liste.
     */
    function getTodoListAll() {
      const posts = getPostsNext30Days();
      return computeTodos(posts);
    }

    function openTodoModal(todo) {
      if (todo.postId) {
        window.dispatchEvent(
          new CustomEvent("trenddash-open-post-modal", { detail: { postId: todo.postId } })
        );
        return;
      }
      openTodoDetailModal(todo);
    }

    function openTodoDetailModal(todo) {
      if (!todoDetailModal) return;
      const titleEl = todoDetailModal.querySelector("[data-todo-modal-title]");
      const explanationEl = todoDetailModal.querySelector("[data-todo-modal-explanation]");
      const contextEl = todoDetailModal.querySelector("[data-todo-modal-context]");
      const actionEl = todoDetailModal.querySelector("[data-todo-modal-action]");
      const buttonsEl = todoDetailModal.querySelector("[data-todo-modal-buttons]");
      if (titleEl) titleEl.textContent = todo.text;
      if (explanationEl) explanationEl.textContent = todo.explanation || "";
      if (contextEl) contextEl.textContent = todo.context || "";
      if (actionEl) actionEl.textContent = todo.action || "";
      buttonsEl.innerHTML = "";
      (todo.buttons || []).forEach((btnType) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "td-button td-button--primary";
        if (btnType === "ai-ideas") {
          btn.textContent = "Zu AI-Videoideen";
          btn.onclick = () => {
            closeTodoModal();
            document.querySelector(".dash-ai-card")?.scrollIntoView({ behavior: "smooth" });
          };
        } else if (btnType === "plan-now") {
          btn.textContent = "Video jetzt einplanen";
          btn.onclick = () => {
            closeTodoModal();
            window.location.href =
              document.querySelector('a[href*="planner"]')?.href || "/planner";
          };
        } else if (btnType === "open-video") {
          btn.textContent = "Zum Video";
          btn.onclick = () => {
            closeTodoModal();
            if (todo.postId) {
              window.dispatchEvent(
                new CustomEvent("trenddash-open-post-modal", {
                  detail: { postId: todo.postId },
                })
              );
            }
          };
        }
        buttonsEl.appendChild(btn);
      });
      todoDetailModal.classList.add("is-open");
      todoDetailModal.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    }

    function closeTodoModal() {
      if (!todoDetailModal) return;
      todoDetailModal.classList.remove("is-open");
      todoDetailModal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    }

    function recalcAndRender() {
      const fullList = getTodoListDashboard();
      const newKeys = new Set(fullList.map((t) => t.key));
      const toRemove = [];
      if (wrapper) {
        Array.from(wrapper.querySelectorAll(".todo-item-wrap")).forEach((wrap) => {
          const key = wrap.dataset.todoKey;
          if (key && !newKeys.has(key) && !dismissedKeys.has(key)) toRemove.push(wrap);
        });
      }
      if (toRemove.length > 0) {
        let done = 0;
        toRemove.forEach((wrap) => {
          wrap.classList.add("todo-item--leaving");
          wrap.addEventListener(
            "transitionend",
            () => {
              wrap.remove();
              done++;
              if (done === toRemove.length) doRender(fullList);
            },
            { once: true }
          );
        });
      } else {
        doRender(fullList);
      }
    }

    function doRender(fullDashboardList) {
      const list = fullDashboardList.filter((t) => !dismissedKeys.has(t.key));
      if (emptyEl) emptyEl.hidden = list.length > 0;
      const top5 = list.slice(0, DASHBOARD_SHOW_COUNT);
      renderTodoList(wrapper, top5, dismissedKeys, {
        openTodoModal,
        onDismiss: (wrap) => animateOutAndRemove(wrap),
      });
      if (showAllBtn) showAllBtn.hidden = list.length === 0;
    }

    function openAllOverlay() {
      if (!todoOverlay) return;
      const fullList = getTodoListAll().filter((t) => !dismissedKeys.has(t.key));
      todoOverlayList.innerHTML = "";
      fullList.forEach((todo) => {
        const row = document.createElement("div");
        const level = getPriorityLevel(todo);
        row.className = "todo-overlay-row " + priorityClass(level);
        const deadlineLabel =
          todo.deadline == null
            ? "—"
            : todo.daysUntil == null
              ? "—"
              : todo.daysUntil < 0
                ? "Überfällig"
                : todo.daysUntil === 0
                  ? "Heute"
                  : todo.daysUntil === 1
                    ? "Morgen"
                    : "In " + todo.daysUntil + " Tagen";
        row.innerHTML =
          '<span class="todo-overlay-date">' +
          (todo.deadline
            ? new Date(todo.deadline + "T12:00:00").toLocaleDateString("de-DE", {
                weekday: "short",
                day: "2-digit",
                month: "2-digit",
              })
            : "—") +
          "</span>" +
          '<span class="todo-overlay-task">' +
          escapeHtml(todo.text) +
          "</span>" +
          '<span class="todo-overlay-deadline">Deadline: ' +
          escapeHtml(deadlineLabel) +
          "</span>" +
          '<button type="button" class="td-button td-button--primary todo-overlay-action">Aktion</button>";
        const btn = row.querySelector(".todo-overlay-action");
        btn.addEventListener("click", () => {
          closeAllOverlay();
          openTodoModal(todo);
        });
        row.addEventListener("click", (e) => {
          if (e.target !== btn) openTodoModal(todo);
        });
        todoOverlayList.appendChild(row);
      });
      todoOverlay.classList.add("is-open");
      todoOverlay.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    }

    function closeAllOverlay() {
      if (!todoOverlay) return;
      todoOverlay.classList.remove("is-open");
      todoOverlay.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    }

    if (todoDetailModal) {
      todoDetailModal
        .querySelectorAll("[data-todo-modal-close]")
        .forEach((el) => el.addEventListener("click", closeTodoModal));
      todoDetailModal
        .querySelector(".td-modal-backdrop")
        ?.addEventListener("click", closeTodoModal);
    }
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (todoDetailModal && todoDetailModal.classList.contains("is-open"))
          closeTodoModal();
        if (todoOverlay && todoOverlay.classList.contains("is-open")) closeAllOverlay();
      }
    });
    if (todoOverlayClose) todoOverlayClose.addEventListener("click", closeAllOverlay);
    if (todoOverlay && todoOverlay.querySelector(".td-modal-backdrop")) {
      todoOverlay.querySelector(".td-modal-backdrop").addEventListener("click", closeAllOverlay);
    }
    if (showAllBtn) showAllBtn.addEventListener("click", openAllOverlay);

    window.addEventListener("trenddash-planner-updated", recalcAndRender);
    recalcAndRender();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.TrendDashTodos = { computeTodos, getDeadlineLabel, getPriorityLevel };
})();
