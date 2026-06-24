const DEFAULT_LOCATION = "Redwood City";
const formatter = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric"
});
const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit"
});

const setText = (id, value) => {
  document.getElementById(id).textContent = value;
};

const formatTemp = (value) => Number.isFinite(value) ? `${value}°F` : "--";
const formatPercent = (value) => Number.isFinite(value) ? `${value}%` : "--";
const formatOutdoorNote = (location) => location ? `Live outdoor weather for ${location}` : "Live outdoor weather";
const chartState = {
  readings: [],
  hoverReading: null,
  plot: null,
  isDragging: false,
  dragStartX: null,
  dragCurrentX: null,
  zoomStartMs: null,
  zoomEndMs: null
};
const locationState = {
  activeLocation: null,
  locations: []
};

function updateClock() {
  const now = new Date();
  setText("time", timeFormatter.format(now));
  setText("date", formatter.format(now));
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function sendJson(url, method, body) {
  const options = {
    method,
    headers: {
      "Content-Type": "application/json"
    }
  };

  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Request failed: ${response.status}`);
  }

  return response.json();
}

function renderLocationSelect() {
  const select = document.getElementById("location-select");
  const removeSelect = document.getElementById("remove-location-select");
  const removeToggle = document.getElementById("remove-location-toggle");
  const removableLocations = locationState.locations.filter((location) => !location.is_protected);
  select.replaceChildren();
  removeSelect.replaceChildren();

  if (locationState.locations.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No saved spots yet";
    select.append(option);
    removeSelect.append(option.cloneNode(true));
    select.disabled = true;
    removeSelect.disabled = true;
    removeToggle.disabled = true;
    return;
  }

  locationState.locations.forEach((location) => {
    const option = document.createElement("option");
    option.value = location.id;
    option.textContent = `${location.nickname} - ${location.location}`;
    select.append(option);
  });

  removableLocations.forEach((location) => {
    const option = document.createElement("option");
    option.value = location.id;
    option.textContent = `${location.nickname} - ${location.location}`;
    removeSelect.append(option);
  });

  select.disabled = false;
  removeSelect.disabled = removableLocations.length === 0;
  removeToggle.disabled = removableLocations.length === 0;

  if (locationState.activeLocation) {
    select.value = String(locationState.activeLocation.id);
  }

  if (removableLocations.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No removable spots";
    removeSelect.append(option);
  }
}

function setLocationFormVisible(isVisible) {
  const panel = document.getElementById("location-panel");
  const removePanel = document.getElementById("remove-location-panel");
  const form = document.getElementById("location-form");
  const toggle = document.getElementById("add-location-toggle");
  const removeToggle = document.getElementById("remove-location-toggle");

  panel.classList.toggle("is-hidden", !isVisible);
  removePanel.classList.add("is-hidden");
  toggle.hidden = isVisible;
  removeToggle.hidden = isVisible;

  if (isVisible) {
    document.getElementById("location-nickname").focus();
  } else {
    form.reset();
  }
}

function setRemoveLocationFormVisible(isVisible) {
  const panel = document.getElementById("location-panel");
  const removePanel = document.getElementById("remove-location-panel");
  const toggle = document.getElementById("add-location-toggle");
  const removeToggle = document.getElementById("remove-location-toggle");

  removePanel.classList.toggle("is-hidden", !isVisible);
  panel.classList.add("is-hidden");
  toggle.hidden = isVisible;
  removeToggle.hidden = isVisible;

  if (isVisible) {
    document.getElementById("remove-location-select").focus();
  }
}

async function loadLocations() {
  const data = await fetchJson("/api/locations");
  locationState.activeLocation = data.active_location;
  locationState.locations = data.locations || [];
  renderLocationSelect();
}

async function activateLocation(locationId) {
  if (!locationId) {
    return;
  }

  const location = await sendJson("/api/locations/active", "PUT", { location_id: locationId });
  locationState.activeLocation = location;
  locationState.locations = locationState.locations.map((item) => ({
    ...item,
    is_active: item.id === location.id
  }));
  renderLocationSelect();
  if (location.outdoor_current) {
    setText("outdoor-temp", formatTemp(location.outdoor_current.temperature));
    setText("outdoor-note", formatOutdoorNote(location.outdoor_current.location));
  }
  loadDashboard();
}

async function saveLocation(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const nickname = form.nickname.value.trim();
  const location = form.location.value.trim();

  if (!nickname || !location) {
    setText("status", "Enter a nickname and location.");
    return;
  }

  try {
    const savedLocation = await sendJson("/api/locations", "POST", { nickname, location });
    form.reset();
    setLocationFormVisible(false);
    locationState.activeLocation = savedLocation;
    await loadLocations();
    loadDashboard();
  } catch (error) {
    setText("status", error.message);
  }
}

async function removeLocation(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const locationId = form.location_id.value;

  if (!locationId) {
    setText("status", "Choose a spot to remove.");
    return;
  }

  try {
    await sendJson(`/api/locations/${encodeURIComponent(locationId)}`, "DELETE");
    setRemoveLocationFormVisible(false);
    await loadLocations();
    loadDashboard();
  } catch (error) {
    setText("status", error.message);
  }
}

function getChartPoints(readings, key) {
  return readings
    .map((reading) => ({
      date: new Date(reading.recorded_at),
      value: Number(reading[key])
    }))
    .filter((point) => !Number.isNaN(point.date.getTime()) && Number.isFinite(point.value));
}

function formatTime(value) {
  return value.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit"
  });
}

function drawLine(ctx, points, xForDate, yForValue, color) {
  if (points.length === 0) {
    return;
  }

  ctx.beginPath();
  points.forEach((point, index) => {
    const x = xForDate(point.date);
    const y = yForValue(point.value);

    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();
}

function getChartReadings() {
  return chartState.readings
    .map((reading) => {
      const date = new Date(reading.recorded_at);
      const indoor = Number(reading.inside_temperature);
      const outdoor = Number(reading.outside_temperature);

      return {
        date,
        indoor: indoor >= 60 ? indoor : null,
        outdoor: Number.isFinite(outdoor) ? outdoor : null
      };
    })
    .filter((reading) => {
      const hasDate = !Number.isNaN(reading.date.getTime());
      return hasDate && (Number.isFinite(reading.indoor) || Number.isFinite(reading.outdoor));
    });
}

function getVisibleChartReadings(chartReadings) {
  if (!Number.isFinite(chartState.zoomStartMs) || !Number.isFinite(chartState.zoomEndMs)) {
    return chartReadings;
  }

  return chartReadings.filter((reading) => {
    const time = reading.date.getTime();
    return time >= chartState.zoomStartMs && time <= chartState.zoomEndMs;
  });
}

function drawHoverMarker(ctx, reading, xForDate, yForValue, top, bottom) {
  if (!reading) {
    return;
  }

  const x = xForDate(reading.date);

  ctx.beginPath();
  ctx.moveTo(x, top);
  ctx.lineTo(x, bottom);
  ctx.strokeStyle = "rgba(100, 112, 109, 0.5)";
  ctx.lineWidth = 1;
  ctx.stroke();

  [
    { value: reading.outdoor, color: "#d96c3b" },
    { value: reading.indoor, color: "#167a75" }
  ].forEach((point) => {
    if (!Number.isFinite(point.value)) {
      return;
    }

    ctx.beginPath();
    ctx.arc(x, yForValue(point.value), 5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.strokeStyle = point.color;
    ctx.lineWidth = 3;
    ctx.stroke();
  });
}

function drawHourlyLines(ctx, minDate, maxDate, xForDate, top, bottom, chartWidth) {
  const hourMs = 60 * 60 * 1000;
  const firstHour = Math.ceil(minDate / hourMs) * hourMs;
  const labelEvery = chartWidth < 640 ? 3 : 2;
  let hourIndex = 0;

  ctx.textBaseline = "alphabetic";
  ctx.textAlign = "center";

  for (let time = firstHour; time <= maxDate; time += hourMs) {
    const x = xForDate(new Date(time));

    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.strokeStyle = "rgba(220, 229, 225, 0.85)";
    ctx.lineWidth = 1;
    ctx.stroke();

    if (hourIndex % labelEvery === 0) {
      ctx.fillStyle = "#64706d";
      ctx.fillText(formatTime(new Date(time)), x, bottom + 12);
    }

    hourIndex += 1;
  }
}

function drawDragSelection(ctx, plot) {
  if (!chartState.isDragging || !Number.isFinite(chartState.dragStartX) || !Number.isFinite(chartState.dragCurrentX)) {
    return;
  }

  const startX = Math.min(chartState.dragStartX, chartState.dragCurrentX);
  const endX = Math.max(chartState.dragStartX, chartState.dragCurrentX);
  const left = Math.max(startX, plot.left);
  const right = Math.min(endX, plot.right);

  if (right - left < 2) {
    return;
  }

  ctx.fillStyle = "rgba(22, 122, 117, 0.12)";
  ctx.fillRect(left, plot.top, right - left, plot.bottom - plot.top);
  ctx.strokeStyle = "rgba(22, 122, 117, 0.56)";
  ctx.lineWidth = 1;
  ctx.strokeRect(left, plot.top, right - left, plot.bottom - plot.top);
}

function drawTemperatureChart() {
  const canvas = document.getElementById("temperature-chart");
  const emptyMessage = document.getElementById("chart-empty");
  const resetButton = document.getElementById("chart-reset");
  const title = document.getElementById("chart-title");
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const chartReadings = getChartReadings();
  const visibleReadings = getVisibleChartReadings(chartReadings);
  const indoorPoints = visibleReadings
    .filter((reading) => Number.isFinite(reading.indoor))
    .map((reading) => ({ date: reading.date, value: reading.indoor }));
  const outdoorPoints = visibleReadings
    .filter((reading) => Number.isFinite(reading.outdoor))
    .map((reading) => ({ date: reading.date, value: reading.outdoor }));
  const points = [...indoorPoints, ...outdoorPoints];

  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  resetButton.classList.toggle("is-hidden", !Number.isFinite(chartState.zoomStartMs));
  title.textContent = Number.isFinite(chartState.zoomStartMs) ? "Zoomed range" : "Past 12 hours";

  if (points.length < 2) {
    chartState.plot = null;
    emptyMessage.textContent = points.length === 1 ? "Need more readings to draw a chart." : "No temperature history yet.";
    emptyMessage.classList.remove("is-hidden");
    return;
  }

  emptyMessage.classList.add("is-hidden");

  const padding = {
    top: 14,
    right: 16,
    bottom: 42,
    left: 56
  };
  const chartWidth = rect.width - padding.left - padding.right;
  const chartHeight = rect.height - padding.top - padding.bottom;
  const temperatures = points.map((point) => point.value);
  const dates = visibleReadings.map((reading) => reading.date.getTime());
  const minTemp = Math.floor(Math.min(...temperatures) - 2);
  const maxTemp = Math.ceil(Math.max(...temperatures) + 2);
  const minDate = Number.isFinite(chartState.zoomStartMs) ? chartState.zoomStartMs : Math.min(...dates);
  const maxDate = Number.isFinite(chartState.zoomEndMs) ? chartState.zoomEndMs : Math.max(...dates);
  const tempRange = maxTemp - minTemp || 1;
  const dateRange = maxDate - minDate || 1;
  const xForDate = (date) => padding.left + ((date.getTime() - minDate) / dateRange) * chartWidth;
  const dateForX = (x) => new Date(minDate + ((x - padding.left) / chartWidth) * dateRange);
  const yForValue = (value) => padding.top + ((maxTemp - value) / tempRange) * chartHeight;
  chartState.plot = {
    chartReadings: visibleReadings,
    left: padding.left,
    right: padding.left + chartWidth,
    top: padding.top,
    bottom: padding.top + chartHeight,
    minDate,
    maxDate,
    xForDate,
    dateForX
  };

  ctx.font = "12px Inter, ui-sans-serif, system-ui, sans-serif";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#64706d";
  ctx.strokeStyle = "#dce5e1";
  ctx.lineWidth = 1;

  drawHourlyLines(ctx, minDate, maxDate, xForDate, padding.top, padding.top + chartHeight, chartWidth);

  for (let index = 0; index <= 4; index += 1) {
    const ratio = index / 4;
    const y = padding.top + chartHeight * ratio;
    const temp = Math.round(maxTemp - tempRange * ratio);

    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(padding.left + chartWidth, y);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(`${temp}°`, padding.left - 10, y);
  }

  drawLine(ctx, outdoorPoints, xForDate, yForValue, "#d96c3b");
  drawLine(ctx, indoorPoints, xForDate, yForValue, "#167a75");
  drawHoverMarker(ctx, chartState.hoverReading, xForDate, yForValue, padding.top, padding.top + chartHeight);
  drawDragSelection(ctx, chartState.plot);
}

function setChartReadout(reading) {
  const readout = document.getElementById("chart-readout");

  if (!reading) {
    readout.textContent = "";
    return;
  }

  readout.innerHTML = `
    <strong>${reading.date.toLocaleString()}</strong>
    &nbsp; Indoor: ${formatTemp(reading.indoor)}
    &nbsp; Outdoor: ${formatTemp(reading.outdoor)}
  `;
}

function clearChartHover() {
  chartState.hoverReading = null;
  setChartReadout(null);
  drawTemperatureChart();
}

function getClosestReadingAtX(x) {
  const plot = chartState.plot;

  if (!plot || plot.chartReadings.length === 0 || x < plot.left || x > plot.right) {
    return null;
  }

  return plot.chartReadings.reduce((best, reading) => {
    const distance = Math.abs(plot.xForDate(reading.date) - x);
    return !best || distance < best.distance ? { reading, distance } : best;
  }, null).reading;
}

function handleChartPointerMove(event) {
  const canvas = document.getElementById("temperature-chart");
  const plot = chartState.plot;

  if (!plot || plot.chartReadings.length === 0) {
    return;
  }

  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;

  if (chartState.isDragging) {
    chartState.dragCurrentX = x;
    drawTemperatureChart();
    return;
  }

  if (x < plot.left || x > plot.right) {
    clearChartHover();
    return;
  }

  chartState.hoverReading = getClosestReadingAtX(x);
  drawTemperatureChart();
  setChartReadout(chartState.hoverReading);
}

function handleChartPointerDown(event) {
  const canvas = document.getElementById("temperature-chart");
  const plot = chartState.plot;

  if (!plot) {
    return;
  }

  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;

  if (x < plot.left || x > plot.right) {
    return;
  }

  chartState.isDragging = true;
  chartState.dragStartX = x;
  chartState.dragCurrentX = x;
  canvas.setPointerCapture(event.pointerId);
}

function handleChartPointerUp(event) {
  const plot = chartState.plot;

  if (!chartState.isDragging || !plot) {
    return;
  }

  const startX = Math.max(Math.min(chartState.dragStartX, chartState.dragCurrentX), plot.left);
  const endX = Math.min(Math.max(chartState.dragStartX, chartState.dragCurrentX), plot.right);
  const selectionWidth = endX - startX;

  chartState.isDragging = false;
  chartState.dragStartX = null;
  chartState.dragCurrentX = null;

  if (selectionWidth > 18) {
    chartState.zoomStartMs = plot.dateForX(startX).getTime();
    chartState.zoomEndMs = plot.dateForX(endX).getTime();
    chartState.hoverReading = null;
    setChartReadout(null);
  }

  if (event.currentTarget.hasPointerCapture(event.pointerId)) {
    event.currentTarget.releasePointerCapture(event.pointerId);
  }
  drawTemperatureChart();
}

function resetChartZoom() {
  chartState.zoomStartMs = null;
  chartState.zoomEndMs = null;
  chartState.hoverReading = null;
  setChartReadout(null);
  drawTemperatureChart();
}

async function loadTemperatureHistory() {
  try {
    const history = await fetchJson("/api/readings/history?hours=12");
    chartState.readings = history.readings || [];
  } catch (error) {
    chartState.readings = [];
    setText("chart-empty", "Could not load temperature history.");
  }

  drawTemperatureChart();
}

async function loadDashboard() {
  let location = DEFAULT_LOCATION;

  try {
    await loadLocations();
    const latest = await fetchJson("/api/readings/latest");
    const activeLocation = latest.active_location || locationState.activeLocation;
    location = activeLocation ? activeLocation.location : latest.location || DEFAULT_LOCATION;

    if (latest.reading) {
      setText("indoor-temp", formatTemp(latest.reading.inside_temperature));
      setText("indoor-humidity", formatPercent(latest.reading.inside_humidity));
      setText("outdoor-temp", formatTemp(latest.reading.outside_temperature));
      setText("outdoor-note", "From latest saved reading");
      setText("status", `Latest sensor update: ${new Date(latest.reading.recorded_at).toLocaleString()}`);
    } else {
      setText("indoor-temp", "--");
      setText("indoor-humidity", "--");
      setText("status", "No indoor readings saved yet.");
    }
  } catch (error) {
    setText("status", "Could not load saved readings.");
  }

  try {
    const weather = await fetchJson(`/api/outdoor/current?location=${encodeURIComponent(location)}`);
    setText("outdoor-temp", formatTemp(weather.temperature));
    setText("outdoor-note", formatOutdoorNote(weather.location));
  } catch (error) {
    setText("outdoor-note", "Outdoor weather unavailable");
  }

  loadTemperatureHistory();
}

updateClock();
setInterval(updateClock, 1000);
loadDashboard();
setInterval(loadDashboard, 60000);
window.addEventListener("resize", drawTemperatureChart);
document.getElementById("chart-reset").addEventListener("click", resetChartZoom);
document.getElementById("location-select").addEventListener("change", (event) => activateLocation(event.target.value));
document.getElementById("add-location-toggle").addEventListener("click", () => setLocationFormVisible(true));
document.getElementById("remove-location-toggle").addEventListener("click", () => setRemoveLocationFormVisible(true));
document.getElementById("cancel-location").addEventListener("click", () => setLocationFormVisible(false));
document.getElementById("cancel-remove-location").addEventListener("click", () => setRemoveLocationFormVisible(false));
document.getElementById("location-form").addEventListener("submit", saveLocation);
document.getElementById("remove-location-form").addEventListener("submit", removeLocation);
document.getElementById("temperature-chart").addEventListener("pointerdown", handleChartPointerDown);
document.getElementById("temperature-chart").addEventListener("pointermove", handleChartPointerMove);
document.getElementById("temperature-chart").addEventListener("pointerup", handleChartPointerUp);
document.getElementById("temperature-chart").addEventListener("pointercancel", handleChartPointerUp);
document.getElementById("temperature-chart").addEventListener("pointerleave", clearChartHover);
document.getElementById("temperature-chart").addEventListener("dblclick", resetChartZoom);
