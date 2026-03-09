/**
 * TrendDash – To-Do-Engine (nächste 30 Tage).
 * Datenquelle: getPostsNext30Days() (gleiche Quelle wie Kalender "Diese Woche").
 * Status-Flow: Idee → Filmen → Editing → Review (Prüfen) → Ready.
 * Regeln: Produktion/Deadlines pro Post + Content-Gaps pro Woche (3 Videos/Woche).
 * Vanilla JS, Kommentare auf Deutsch.
 */
(function () {
  const VIDEOS_PER_WEEK = 3;
  const DASHBOARD_SHOW_COUNT = 5;
  const PRIO_KRITISCH = 0;
  const PRIO_HOCH = 1;
  const PRIO_MITTEL = 2;
  const PRIO_NIEDRIG = 3;

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

  function getISOWeekNumber(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.floor(((d - yearStart) / 86400000 + 1) / 7);
  }

  /**
   * Generiert alle To-Dos: Produktion (pro Post) + Content-Gaps (pro Woche).
   * daysLeft = (Upload-Datum − heute) in vollen Tagen.
   * Priorität: kritisch → hoch → mittel → niedrig.
   */
  function computeTodos(posts) {
    if (!posts || !Array.isArray(posts)) return [];
    const today = startOfDay(new Date());
    const todos = [];
    const seenKeys = new Set();

    function daysLeft(iso) {
      const d = new Date(iso + "T12:00:00");
      return Math.ceil((startOfDay(d) - today) / 86400000);
    }

    function dateLabel(iso) {
      return new Date(iso + "T12:00:00").toLocaleDateString("de-DE", {
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
      });
    }

    // —— PRODUKTION / DEADLINES (pro Post) ——
    for (const { post, dateISO } of posts) {
      const status = (post.status || "").toLowerCase();
      if (status === "posted") continue;
      const dl = daysLeft(dateISO);
      const title = post.title || "Ohne Titel";
      const label = dateLabel(dateISO);

      // KRITISCH: Heute/Überfällig, nicht READY
      if (dl <= 0 && status !== "ready") {
        const key = "post-" + post.id + "-not-ready";
        if (!seenKeys.has(key)) {
          seenKeys.add(key);
          todos.push({
            key,
            type: "not-ready",
            postId: post.id,
            priority: "kritisch",
            priorityLevel: "red",
            sortOrder: PRIO_KRITISCH,
            daysUntil: dl,
            deadline: dateISO,
            text: "Heute Upload: „" + title + "“ ist nicht READY",
            hint: dl < 0 ? "Überfällig " + label : "Heute " + label,
            explanation: "Das Video sollte auf „Ready“ stehen.",
            context: dl < 0 ? "Upload überfällig" : "Upload heute",
            action: "Status auf „Ready“ setzen oder Post verschieben.",
            buttons: ["open-video"],
          });
        }
      }

      // HOCH: Morgen Upload → heute in REVIEW/READY
      if (dl === 1 && ["idea", "filming", "editing"].indexOf(status) !== -1) {
        const key = "post-" + post.id + "-tomorrow";
        if (!seenKeys.has(key)) {
          seenKeys.add(key);
          todos.push({
            key,
            type: "must-review-tomorrow",
            postId: post.id,
            priority: "hoch",
            priorityLevel: "yellow",
            sortOrder: PRIO_HOCH,
            daysUntil: 1,
            deadline: dateISO,
            text: "Morgen Upload: „" + title + "“ muss heute in Prüfen/READY",
            hint: "Upload " + label,
            explanation: "Ein Tag vor Upload sollte das Video in Review oder Ready sein.",
            context: "Upload morgen",
            action: "Status auf „Prüfen“ oder „Ready“ setzen.",
            buttons: ["open-video"],
          });
        }
      }

      // HOCH: In 2 Tagen Upload → spätestens heute in EDITING
      if (dl === 2 && ["idea", "filming"].indexOf(status) !== -1) {
        const key = "post-" + post.id + "-editing";
        if (!seenKeys.has(key)) {
          seenKeys.add(key);
          todos.push({
            key,
            type: "must-edit",
            postId: post.id,
            priority: "hoch",
            priorityLevel: "yellow",
            sortOrder: PRIO_HOCH,
            daysUntil: 2,
            deadline: dateISO,
            text: "In 2 Tagen Upload: „" + title + "“ muss spätestens heute in EDITING",
            hint: "Upload " + label,
            explanation: "Zwei Tage vor Upload sollte der Schnitt laufen.",
            context: "Upload in 2 Tagen",
            action: "Video schneiden, Status auf „Editing“ setzen.",
            buttons: ["open-video"],
          });
        }
      }

      // MITTEL: In 3 Tagen Upload → muss gefilmt werden
      if (dl === 3 && status === "idea") {
        const key = "post-" + post.id + "-film";
        if (!seenKeys.has(key)) {
          seenKeys.add(key);
          todos.push({
            key,
            type: "must-film",
            postId: post.id,
            priority: "mittel",
            priorityLevel: "blue",
            sortOrder: PRIO_MITTEL,
            daysUntil: 3,
            deadline: dateISO,
            text: "In 3 Tagen Upload: „" + title + "“ muss gefilmt werden",
            hint: "Upload " + label,
            explanation: "Drei Tage vor Upload sollte das Video in Produktion sein.",
            context: "Upload in 3 Tagen",
            action: "Video filmen, Status auf „Filmen“ setzen.",
            buttons: ["open-video"],
          });
        }
      }

      // Schnitt fertigstellen (EDITING, daysLeft <= 2)
      if (status === "editing" && dl <= 2) {
        const key = "post-" + post.id + "-schnitt";
        if (!seenKeys.has(key)) {
          seenKeys.add(key);
          todos.push({
            key,
            type: "must-edit-schnitt",
            postId: post.id,
            priority: dl <= 0 ? "kritisch" : "hoch",
            priorityLevel: dl <= 0 ? "red" : "yellow",
            sortOrder: dl <= 0 ? PRIO_KRITISCH : PRIO_HOCH,
            daysUntil: dl,
            deadline: dateISO,
            text: "Schnitt fertigstellen: „" + title + "“",
            hint: "Upload " + label,
            explanation: "Video schneiden und in Prüfen/Ready bringen.",
            context: "Upload " + (dl <= 0 ? "heute/überfällig" : "bald"),
            action: "Editing abschließen, Status auf „Prüfen“ setzen.",
            buttons: ["open-video"],
          });
        }
      }

      // Review durchführen (Prüfen) (REVIEW, daysLeft <= 1)
      if (status === "review" && dl <= 1) {
        const key = "post-" + post.id + "-pruefen";
        if (!seenKeys.has(key)) {
          seenKeys.add(key);
          todos.push({
            key,
            type: "must-review",
            postId: post.id,
            priority: dl <= 0 ? "kritisch" : "hoch",
            priorityLevel: dl <= 0 ? "red" : "yellow",
            sortOrder: dl <= 0 ? PRIO_KRITISCH : PRIO_HOCH,
            daysUntil: dl,
            deadline: dateISO,
            text: "Prüfen: „" + title + "“",
            hint: "Upload " + label,
            explanation: "Letzte Prüfung und Freigabe auf „Ready“.",
            context: "Upload " + (dl <= 0 ? "heute" : "morgen"),
            action: "Review durchführen, Status auf „Ready“ setzen.",
            buttons: ["open-video"],
          });
        }
      }
    }

    // —— CONTENT-GAPS (pro Woche, Ziel 3 Videos) ——
    const weekStart = getMonday(today);
    for (let w = 0; w < 5; w++) {
      const weekMonday = new Date(weekStart);
      weekMonday.setDate(weekStart.getDate() + w * 7);
      const weekSunday = new Date(weekMonday);
      weekSunday.setDate(weekMonday.getDate() + 6);
      const weekStartISO = weekMonday.getFullYear() + "-" + String(weekMonday.getMonth() + 1).padStart(2, "0") + "-" + String(weekMonday.getDate()).padStart(2, "0");
      let count = 0;
      for (const { dateISO } of posts) {
        const postDay = startOfDay(new Date(dateISO + "T12:00:00"));
        if (postDay >= weekMonday && postDay <= weekSunday) count++;
      }
      if (count >= VIDEOS_PER_WEEK) continue;
      const missing = VIDEOS_PER_WEEK - count;
      const kw = getISOWeekNumber(weekMonday);
      const isCurrentWeek = w === 0;
      const key = "gap-kw-" + weekStartISO;
      if (!seenKeys.has(key)) {
        seenKeys.add(key);
        todos.push({
          key,
          type: "weekly-goal",
          priority: isCurrentWeek ? "mittel" : "niedrig",
          priorityLevel: "blue",
          sortOrder: isCurrentWeek ? PRIO_MITTEL : PRIO_NIEDRIG,
          daysUntil: null,
          deadline: null,
          weekStartISO,
          weekNum: kw,
          text: isCurrentWeek ? "Diese Woche fehlen noch " + missing + " Video(s)." : "In KW " + kw + " fehlen noch " + missing + " Video(s).",
          hint: "Woche " + weekMonday.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) + " – " + weekSunday.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }),
          explanation: "Mindestens " + VIDEOS_PER_WEEK + " Videos pro Woche einplanen.",
          context: "Aktuell " + count + " von " + VIDEOS_PER_WEEK + " geplant.",
          action: "Weitere Videos einplanen oder AI-Videoideen nutzen.",
          buttons: ["ai-ideas"],
        });
      }
    }

    // Sortierung: kritisch → hoch → mittel → niedrig, dann daysUntil
    todos.sort((a, b) => {
      const pa = a.sortOrder ?? PRIO_NIEDRIG;
      const pb = b.sortOrder ?? PRIO_NIEDRIG;
      if (pa !== pb) return pa - pb;
      const da = a.daysUntil == null ? 999 : a.daysUntil;
      const db = b.daysUntil == null ? 999 : b.daysUntil;
      if (da !== db) return da - db;
      return (a.priorityLevel === "red" ? 0 : a.priorityLevel === "yellow" ? 1 : 2) - (b.priorityLevel === "red" ? 0 : b.priorityLevel === "yellow" ? 1 : 2);
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
      const deadlineClass =
        deadlineLabel === "" ? "" : " todo-deadline--" + level;
      const deadlineHtml =
        deadlineLabel === ""
          ? ""
          : '<span class="todo-deadline' + deadlineClass + '">Deadline: ' + escapeHtml(deadlineLabel) + "</span>";
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
    const todoCards = [];
    document.querySelectorAll(".dash-todos-card").forEach((card) => {
      const wrapper = card.querySelector(".todo-list-wrapper");
      const emptyEl = card.querySelector(".todo-empty");
      const showAllBtn = card.querySelector(".todo-show-all-btn");
      if (wrapper) todoCards.push({ wrapper, emptyEl, showAllBtn });
    });

    const todoDetailModal = document.getElementById("todoDetailModal");
    const todoOverlay = document.getElementById("todoAllOverlay");
    const todoOverlayList = document.getElementById("todoAllOverlayList");
    const todoOverlayClose = document.querySelector("[data-todo-overlay-close]");

    const dismissedKeys = new Set();
    const getPostsNext30Days =
      window.TrendDashPlanner && window.TrendDashPlanner.getPostsNext30Days;
    if (typeof getPostsNext30Days !== "function") {
      todoCards.forEach(({ emptyEl }) => {
        if (emptyEl) {
          emptyEl.hidden = false;
          emptyEl.textContent = "Wochenplan-Daten nicht geladen.";
        }
      });
      return;
    }

    /**
     * Dashboard: getPostsNext30Days() → computeTodos → sortiert.
     * Rückgabe: komplette Liste (Anzeige auf 5 wird in doRender begrenzt).
     */
    function getTodoListDashboard() {
      const posts = getPostsNext30Days();
      const list = computeTodos(posts);
      if (typeof console !== "undefined" && console.log) {
        console.log("[To-Do Engine] Anzahl posts30:", posts.length);
        console.log("[To-Do Engine] Anzahl todos erzeugt:", list.length);
        list.slice(0, 3).forEach(function (t, i) {
          console.log("[To-Do Engine] Top " + (i + 1) + ":", t.text, "| Priorität:", t.priority || t.priorityLevel);
        });
      }
      return list;
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
      todoCards.forEach(({ wrapper }) => {
        if (!wrapper) return;
        Array.from(wrapper.querySelectorAll(".todo-item-wrap")).forEach((wrap) => {
          const key = wrap.dataset.todoKey;
          if (key && !newKeys.has(key) && !dismissedKeys.has(key)) wrap.remove();
        });
      });
      doRender(fullList);
    }

    function doRender(fullDashboardList) {
      const list = fullDashboardList.filter((t) => !dismissedKeys.has(t.key));
      todoCards.forEach(({ wrapper, emptyEl, showAllBtn }) => {
        if (emptyEl) emptyEl.hidden = list.length > 0;
        if (wrapper) {
          if (list.length === 0) {
            wrapper.innerHTML = "";
          } else {
            const top5 = list.slice(0, DASHBOARD_SHOW_COUNT);
            renderTodoList(wrapper, top5, dismissedKeys, {
              openTodoModal,
              onDismiss: (wrap) => animateOutAndRemove(wrap),
            });
          }
        }
        if (showAllBtn) showAllBtn.hidden = list.length === 0;
      });
      window.dispatchEvent(
        new CustomEvent("trenddash-todo-count", { detail: { count: list.length } })
      );
    }

    function openAllOverlay() {
      if (!todoOverlay || !todoOverlayList) return;
      const fullList = getTodoListAll().filter((t) => !dismissedKeys.has(t.key));
      todoOverlayList.innerHTML = "";
      const kritisch = fullList.filter((t) => t.priority === "kritisch" || (t.daysUntil != null && t.daysUntil <= 0));
      const dieseWoche = fullList.filter(
        (t) =>
          kritisch.indexOf(t) === -1 &&
          ((t.priority === "hoch" || t.priority === "mittel") || (t.daysUntil != null && t.daysUntil >= 1 && t.daysUntil <= 7))
      );
      const restList = fullList.filter((t) => kritisch.indexOf(t) === -1 && dieseWoche.indexOf(t) === -1);
      function addOverlayRow(todo) {
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
          '<button type="button" class="td-button td-button--primary todo-overlay-action">Aktion</button>';
        const btn = row.querySelector(".todo-overlay-action");
        btn.addEventListener("click", () => {
          closeAllOverlay();
          openTodoModal(todo);
        });
        row.addEventListener("click", (e) => {
          if (e.target !== btn) openTodoModal(todo);
        });
        todoOverlayList.appendChild(row);
      }
      if (kritisch.length > 0) {
        const h3 = document.createElement("h3");
        h3.className = "todo-overlay-group-title";
        h3.textContent = "Kritisch (Überfällig/Heute)";
        todoOverlayList.appendChild(h3);
        kritisch.forEach((t) => addOverlayRow(t));
      }
      if (dieseWoche.length > 0) {
        const h3b = document.createElement("h3");
        h3b.className = "todo-overlay-group-title";
        h3b.textContent = "Diese Woche";
        todoOverlayList.appendChild(h3b);
        dieseWoche.forEach((t) => addOverlayRow(t));
      }
      if (restList.length > 0) {
        const h3c = document.createElement("h3");
        h3c.className = "todo-overlay-group-title";
        h3c.textContent = "Nächste Wochen";
        todoOverlayList.appendChild(h3c);
        restList.forEach((t) => addOverlayRow(t));
      }
      if (fullList.length === 0) {
        const empty = document.createElement("p");
        empty.className = "todo-overlay-empty";
        empty.textContent = "Keine offenen Aufgaben.";
        todoOverlayList.appendChild(empty);
      }
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
    document.querySelectorAll(".todo-show-all-btn").forEach((btn) => {
      btn.addEventListener("click", openAllOverlay);
    });

    // Realtime-Update: Bei Status-/Plan-Änderung To-Dos und Content-Gaps neu berechnen (ohne Page Reload).
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
