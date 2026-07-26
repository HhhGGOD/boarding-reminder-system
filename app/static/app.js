const state = {
  flights: [],
  selectedFlight: null,
  passengers: [],
  selectedPassengerIds: new Set(),
  config: null,
};

const elements = {
  searchForm: document.querySelector("#searchForm"),
  flightDate: document.querySelector("#flightDate"),
  flightNo: document.querySelector("#flightNo"),
  searchButton: document.querySelector("#searchButton"),
  resetButton: document.querySelector("#resetButton"),
  workspace: document.querySelector("#workspace"),
  initialEmpty: document.querySelector("#initialEmpty"),
  flightSelect: document.querySelector("#flightSelect"),
  passengerRows: document.querySelector("#passengerRows"),
  tableEmpty: document.querySelector("#tableEmpty"),
  tableLoading: document.querySelector("#tableLoading"),
  selectAll: document.querySelector("#selectAll"),
  selectedCount: document.querySelector("#selectedCount"),
  openReminderButton: document.querySelector("#openReminderButton"),
  passengerFilter: document.querySelector("#passengerFilter"),
  refreshButton: document.querySelector("#refreshButton"),
  reminderDialog: document.querySelector("#reminderDialog"),
  reminderForm: document.querySelector("#reminderForm"),
  reminderMessage: document.querySelector("#reminderMessage"),
  sendReminderButton: document.querySelector("#sendReminderButton"),
  logsDialog: document.querySelector("#logsDialog"),
  logsList: document.querySelector("#logsList"),
  toast: document.querySelector("#toast"),
};

const statusLabels = {
  CHECK_IN: "值机开放",
  BOARDING: "正在登机",
  FINAL_CALL: "最后召集",
  DELAYED: "航班延误",
};

const channelLabels = {
  SMS: "短信",
  BROADCAST: "广播",
  PHONE: "人工电话",
};

function localDateValue(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function formatTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "尚未催促";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = "请求失败，请稍后重试";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (_) {
      // Keep the friendly fallback.
    }
    throw new Error(detail);
  }
  return response.json();
}

function toast(message, isError = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("is-error", isError);
  elements.toast.classList.add("is-visible");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(
    () => elements.toast.classList.remove("is-visible"),
    3200,
  );
}

function updateClock() {
  const now = new Date();
  document.querySelector("#clockTime").textContent = now.toLocaleTimeString(
    "zh-CN",
    { hour12: false },
  );
  document.querySelector("#clockDate").textContent =
    new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
    }).format(now);
}

function updateCountdown() {
  if (!state.selectedFlight) return;
  const seconds = Math.round(
    (new Date(state.selectedFlight.boardingCloseAt).getTime() - Date.now()) /
      1000,
  );
  const value = document.querySelector("#closeCountdown");
  const unit = document.querySelector("#countdownUnit");
  if (seconds <= 0) {
    value.textContent = "已到";
    unit.textContent = "关舱时间";
    return;
  }
  if (seconds < 3600) {
    value.textContent = Math.ceil(seconds / 60);
    unit.textContent = "分钟";
  } else {
    value.textContent = (seconds / 3600).toFixed(1);
    unit.textContent = "小时";
  }
}

function updateSelection() {
  const count = state.selectedPassengerIds.size;
  elements.selectedCount.textContent = count;
  elements.openReminderButton.disabled = count === 0;
  elements.selectAll.checked =
    state.passengers.length > 0 && count === state.passengers.length;
  elements.selectAll.indeterminate =
    count > 0 && count < state.passengers.length;
}

function renderPassengers() {
  const keyword = elements.passengerFilter.value.trim().toLowerCase();
  const visible = state.passengers.filter(
    (passenger) =>
      passenger.passengerName.toLowerCase().includes(keyword) ||
      passenger.seatNo.toLowerCase().includes(keyword) ||
      passenger.passengerId.toLowerCase().includes(keyword),
  );

  elements.passengerRows.innerHTML = visible
    .map(
      (passenger) => `
        <tr>
          <td class="check-cell">
            <input
              type="checkbox"
              data-passenger-id="${escapeHtml(passenger.passengerId)}"
              aria-label="选择 ${escapeHtml(passenger.passengerName)}"
              ${state.selectedPassengerIds.has(passenger.passengerId) ? "checked" : ""}
            />
          </td>
          <td>
            <div class="passenger-name">
              <span class="avatar">${escapeHtml(passenger.passengerName.slice(0, 1))}</span>
              <div>
                <strong>${escapeHtml(passenger.passengerName)}</strong>
                <small>${escapeHtml(passenger.passengerId)}</small>
              </div>
            </div>
          </td>
          <td><span class="seat-tag">${escapeHtml(passenger.seatNo)}</span></td>
          <td>${escapeHtml(passenger.passengerType)}</td>
          <td>${escapeHtml(passenger.phoneMasked)}</td>
          <td>${formatTime(passenger.checkedInAt)}</td>
          <td>
            <span class="reminder-time">
              ${
                passenger.lastReminderAt
                  ? `<b>${channelLabels[passenger.lastReminderChannel] || passenger.lastReminderChannel}</b>${formatDateTime(passenger.lastReminderAt)}`
                  : "尚未催促"
              }
            </span>
          </td>
          <td><span class="status-pill">待登机</span></td>
        </tr>
      `,
    )
    .join("");

  elements.tableEmpty.classList.toggle(
    "is-hidden",
    state.passengers.length !== 0,
  );
  updateSelection();
}

function renderFlight(flight) {
  state.selectedFlight = flight;
  document.querySelector("#selectedFlightNo").textContent = flight.flightNo;
  document.querySelector("#origin").textContent = flight.origin;
  document.querySelector("#destination").textContent = flight.destination;
  document.querySelector("#departureTime").textContent = formatTime(
    flight.scheduledDeparture,
  );
  document.querySelector("#gateNo").textContent = flight.gateNo;
  document.querySelector("#flightStatus").textContent =
    statusLabels[flight.status] || flight.status;
  document.querySelector("#checkedInCount").textContent =
    flight.checkedInCount;
  document.querySelector("#boardedCount").textContent = flight.boardedCount;
  document.querySelector("#unboardedCount").textContent =
    flight.unboardedCount;
  updateCountdown();
}

async function loadPassengers() {
  if (!state.selectedFlight) return;
  elements.tableLoading.classList.remove("is-hidden");
  elements.tableEmpty.classList.add("is-hidden");
  elements.passengerRows.innerHTML = "";
  state.selectedPassengerIds.clear();
  updateSelection();
  try {
    const payload = await request(
      `/api/flights/${encodeURIComponent(state.selectedFlight.id)}/unboarded-passengers`,
    );
    state.passengers = payload.items;
    renderPassengers();
    document.querySelector("#lastUpdated").textContent =
      `最近刷新 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
  } catch (error) {
    toast(error.message, true);
  } finally {
    elements.tableLoading.classList.add("is-hidden");
  }
}

async function searchFlights() {
  const query = new URLSearchParams({ date: elements.flightDate.value });
  if (elements.flightNo.value.trim()) {
    query.set("flight_no", elements.flightNo.value.trim().toUpperCase());
  }
  elements.searchButton.disabled = true;
  elements.searchButton.querySelector("span").textContent = "正在查询…";
  try {
    const payload = await request(`/api/flights?${query}`);
    state.flights = payload.items;
    if (!state.flights.length) {
      state.selectedFlight = null;
      elements.workspace.classList.add("is-hidden");
      elements.initialEmpty.classList.remove("is-hidden");
      elements.initialEmpty.querySelector("h3").textContent = "没有找到匹配航班";
      elements.initialEmpty.querySelector("p").textContent =
        "请检查日期和航班号，或尝试只按日期查询。";
      toast("没有找到匹配航班", true);
      return;
    }

    elements.flightSelect.innerHTML = state.flights
      .map(
        (flight) =>
          `<option value="${escapeHtml(flight.id)}">${escapeHtml(flight.flightNo)} · ${escapeHtml(flight.origin)}—${escapeHtml(flight.destination)} · ${formatTime(flight.scheduledDeparture)}</option>`,
      )
      .join("");
    elements.workspace.classList.remove("is-hidden");
    elements.initialEmpty.classList.add("is-hidden");
    renderFlight(state.flights[0]);
    await loadPassengers();
  } catch (error) {
    toast(error.message, true);
  } finally {
    elements.searchButton.disabled = false;
    elements.searchButton.querySelector("span").textContent = "查询未登机旅客";
  }
}

function openReminderDialog() {
  if (!state.selectedPassengerIds.size) return;
  document.querySelector("#modalSelectedCount").textContent =
    `${state.selectedPassengerIds.size} 位旅客`;
  document.querySelector("#modalFlightInfo").textContent =
    `${state.selectedFlight.flightNo} · ${state.selectedFlight.gateNo} 登机口`;
  const message = `温馨提示：您乘坐的 ${state.selectedFlight.flightNo} 航班即将结束登机，请尽快前往 ${state.selectedFlight.gateNo} 登机口。`;
  elements.reminderMessage.value = message;
  document.querySelector("#messageLength").textContent = message.length;
  elements.reminderDialog.showModal();
}

async function sendReminder(event) {
  event.preventDefault();
  const channel = new FormData(elements.reminderForm).get("channel");
  elements.sendReminderButton.disabled = true;
  elements.sendReminderButton.textContent = "正在核验并提交…";
  try {
    const payload = await request("/api/reminders", {
      method: "POST",
      body: JSON.stringify({
        flight_id: state.selectedFlight.id,
        passenger_ids: [...state.selectedPassengerIds],
        channel,
        message: elements.reminderMessage.value.trim(),
      }),
    });
    elements.reminderDialog.close();
    const sent = payload.sent.length;
    const skipped = payload.skipped.length;
    toast(
      sent
        ? `已提交 ${sent} 位旅客的催促${skipped ? `，自动跳过 ${skipped} 位` : ""}`
        : payload.skipped[0]?.reason || "未提交催促",
      sent === 0,
    );
    await loadPassengers();
  } catch (error) {
    toast(error.message, true);
  } finally {
    elements.sendReminderButton.disabled = false;
    elements.sendReminderButton.textContent = "确认发起催促";
  }
}

async function openLogs() {
  if (!state.selectedFlight) return;
  elements.logsList.innerHTML = '<div class="loading-state"><p>正在读取记录…</p></div>';
  elements.logsDialog.showModal();
  try {
    const payload = await request(
      `/api/flights/${encodeURIComponent(state.selectedFlight.id)}/reminders`,
    );
    elements.logsList.innerHTML = payload.items.length
      ? payload.items
          .map(
            (log) => `
            <article class="log-item">
              <time>${formatDateTime(log.remindedAt)}</time>
              <div>
                <strong>${escapeHtml(log.passengerName)} · ${escapeHtml(log.passengerId)}</strong>
                <small>${escapeHtml(log.operatorId)} · ${escapeHtml(log.status)}</small>
              </div>
              <span class="log-channel">${escapeHtml(channelLabels[log.channel] || log.channel)}</span>
            </article>
          `,
          )
          .join("")
      : '<div class="empty-state"><h4>暂无催促记录</h4><p>本航班还没有发起过催促。</p></div>';
  } catch (error) {
    elements.logsList.innerHTML = `<div class="empty-state"><p>${escapeHtml(error.message)}</p></div>`;
  }
}

elements.searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchFlights();
});

document.querySelectorAll("[data-flight]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.flightNo.value = button.dataset.flight;
    searchFlights();
  });
});

elements.resetButton.addEventListener("click", () => {
  elements.flightDate.value = localDateValue();
  elements.flightNo.value = "";
  elements.workspace.classList.add("is-hidden");
  elements.initialEmpty.classList.remove("is-hidden");
  elements.initialEmpty.querySelector("h3").textContent =
    "输入航班信息开始查询";
  elements.initialEmpty.querySelector("p").textContent =
    "系统将关联航班、值机与登机记录，为你筛选出需要关注的旅客。";
});

elements.flightSelect.addEventListener("change", async () => {
  const flight = state.flights.find(
    (item) => item.id === elements.flightSelect.value,
  );
  if (flight) {
    renderFlight(flight);
    await loadPassengers();
  }
});

elements.passengerRows.addEventListener("change", (event) => {
  const checkbox = event.target.closest("[data-passenger-id]");
  if (!checkbox) return;
  if (checkbox.checked) {
    state.selectedPassengerIds.add(checkbox.dataset.passengerId);
  } else {
    state.selectedPassengerIds.delete(checkbox.dataset.passengerId);
  }
  updateSelection();
});

elements.selectAll.addEventListener("change", () => {
  state.selectedPassengerIds.clear();
  if (elements.selectAll.checked) {
    state.passengers.forEach((passenger) =>
      state.selectedPassengerIds.add(passenger.passengerId),
    );
  }
  renderPassengers();
});

elements.passengerFilter.addEventListener("input", renderPassengers);
elements.refreshButton.addEventListener("click", loadPassengers);
elements.openReminderButton.addEventListener("click", openReminderDialog);
elements.reminderForm.addEventListener("submit", sendReminder);
elements.reminderMessage.addEventListener("input", () => {
  document.querySelector("#messageLength").textContent =
    elements.reminderMessage.value.length;
});
elements.viewLogsButton?.addEventListener("click", openLogs);
document.querySelector("#viewLogsButton").addEventListener("click", openLogs);

document.querySelectorAll("[data-close-dialog]").forEach((button) =>
  button.addEventListener("click", () => elements.reminderDialog.close()),
);
document.querySelectorAll("[data-close-logs]").forEach((button) =>
  button.addEventListener("click", () => elements.logsDialog.close()),
);

async function bootstrap() {
  elements.flightDate.value = localDateValue();
  updateClock();
  window.setInterval(updateClock, 1000);
  window.setInterval(updateCountdown, 15000);
  try {
    state.config = await request("/api/config");
  } catch (_) {
    // The search action will surface connectivity errors if necessary.
  }
}

bootstrap();
