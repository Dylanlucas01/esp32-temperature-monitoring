const setText = (id, value) => {
  document.getElementById(id).textContent = value;
};

const formatTemp = (value) => Number.isFinite(value) ? `${value}°F` : "--";
const formatPercent = (value) => Number.isFinite(value) ? `${value}%` : "--";
const ROWS_PER_PAGE = 10;

const readingsState = {
  currentPage: 1,
  pageCount: 1,
  total: 0,
  sortBy: "recorded_at",
  sortDir: "desc"
};

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function padNumber(value, length = 2) {
  return String(value).padStart(length, "0");
}

function getLocalOffset(date) {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteMinutes = Math.abs(offsetMinutes);
  const hours = Math.floor(absoluteMinutes / 60);
  const minutes = absoluteMinutes % 60;

  return `${sign}${padNumber(hours)}:${padNumber(minutes)}`;
}

function formatReadingTime(reading) {
  const date = reading.date;
  const timestamp = [
    date.getFullYear(),
    padNumber(date.getMonth() + 1),
    padNumber(date.getDate())
  ].join("-");
  const time = [
    padNumber(date.getHours()),
    padNumber(date.getMinutes()),
    padNumber(date.getSeconds())
  ].join(":");

  return `${timestamp} ${time}${getLocalOffset(date)}`;
}

function setReadingsTableMessage(message) {
  document.getElementById("readings-table-body").innerHTML = `
    <tr>
      <td colspan="6" class="empty-cell">${message}</td>
    </tr>
  `;
  setText("readings-count", "0 readings");
  document.getElementById("pagination").innerHTML = "";
  updateSortButtons();
}

function updateReadingsCount(visibleCount) {
  if (readingsState.total === 0 || visibleCount === 0) {
    setText("readings-count", "0 readings");
    return;
  }

  const startIndex = (readingsState.currentPage - 1) * ROWS_PER_PAGE + 1;
  const endIndex = Math.min(startIndex + visibleCount - 1, readingsState.total);
  const readingLabel = readingsState.total === 1 ? "reading" : "readings";
  setText("readings-count", `${startIndex}-${endIndex} of ${readingsState.total} ${readingLabel}`);
}

function renderReadingsTable(readings) {
  const tableBody = document.getElementById("readings-table-body");

  if (readings.length === 0) {
    setReadingsTableMessage("No readings saved yet.");
    return;
  }

  updateReadingsCount(readings.length);

  tableBody.innerHTML = readings.map((reading) => `
    <tr>
      <td>${reading.id}</td>
      <td>${formatReadingTime(reading)}</td>
      <td>${formatTemp(reading.inside_temp_f)}</td>
      <td>${formatPercent(reading.inside_humidity)}</td>
      <td>${formatTemp(reading.outside_temp_f)}</td>
      <td>${formatPercent(reading.outside_humidity)}</td>
    </tr>
  `).join("");
  renderPagination();
  updateSortButtons();
}

function normalizeReadings(readings) {
  return readings
    .map((reading) => ({
      ...reading,
      date: new Date(reading.recorded_at)
    }))
    .filter((reading) => !Number.isNaN(reading.date.getTime()));
}

function updatePagination(data) {
  readingsState.currentPage = data.page || 1;
  readingsState.pageCount = data.pages || 1;
  readingsState.total = data.total || 0;
}

function updateSortButtons() {
  document.querySelectorAll(".sort-button").forEach((button) => {
    const isActive = button.dataset.sortBy === readingsState.sortBy;
    button.classList.toggle("is-active", isActive);
    button.dataset.sortDir = isActive ? readingsState.sortDir : "";
    button.setAttribute(
      "aria-sort",
      isActive && readingsState.sortDir === "asc" ? "ascending" : isActive ? "descending" : "none"
    );
  });
}

function getVisiblePages() {
  const pages = new Set([1, readingsState.pageCount]);
  let startPage = Math.max(1, readingsState.currentPage - 1);
  let endPage = Math.min(readingsState.pageCount, readingsState.currentPage + 1);

  if (readingsState.currentPage <= 2) {
    endPage = Math.min(3, readingsState.pageCount);
  }

  if (readingsState.currentPage >= readingsState.pageCount - 1) {
    startPage = Math.max(1, readingsState.pageCount - 2);
  }

  for (let page = startPage; page <= endPage; page += 1) {
    pages.add(page);
  }

  return [...pages]
    .sort((a, b) => a - b);
}

function addPaginationButton(container, label, page, options = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = options.disabled || false;
  button.classList.toggle("is-current", options.current || false);
  button.setAttribute("aria-label", options.ariaLabel || `Go to page ${page}`);

  if (options.current) {
    button.setAttribute("aria-current", "page");
  }

  button.addEventListener("click", () => goToPage(page));
  container.appendChild(button);
}

function renderPagination() {
  const pagination = document.getElementById("pagination");
  const visiblePages = getVisiblePages();
  pagination.innerHTML = "";

  addPaginationButton(pagination, "<", readingsState.currentPage - 1, {
    ariaLabel: "Go to previous page",
    disabled: readingsState.currentPage === 1
  });

  visiblePages.forEach((page, index) => {
    const previousPage = visiblePages[index - 1];
    if (previousPage && page - previousPage > 1) {
      const ellipsis = document.createElement("span");
      ellipsis.textContent = "...";
      ellipsis.className = "pagination-ellipsis";
      pagination.appendChild(ellipsis);
    }

    addPaginationButton(pagination, String(page), page, {
      current: page === readingsState.currentPage
    });
  });

  addPaginationButton(pagination, ">", readingsState.currentPage + 1, {
    ariaLabel: "Go to next page",
    disabled: readingsState.currentPage === readingsState.pageCount
  });
}

function goToPage(page) {
  if (page < 1 || page > readingsState.pageCount || page === readingsState.currentPage) {
    return;
  }

  loadReadings(page);
}

function getReadingsUrl(page) {
  const params = new URLSearchParams({
    page,
    per_page: ROWS_PER_PAGE,
    sort_by: readingsState.sortBy,
    sort_dir: readingsState.sortDir
  });

  return `/api/readings?${params.toString()}`;
}

function setSort(sortBy) {
  if (readingsState.sortBy === sortBy) {
    readingsState.sortDir = readingsState.sortDir === "asc" ? "desc" : "asc";
  } else {
    readingsState.sortBy = sortBy;
    readingsState.sortDir = sortBy === "recorded_at" ? "desc" : "asc";
  }

  loadReadings(1);
}

async function loadReadings(page = readingsState.currentPage) {
  try {
    const data = await fetchJson(getReadingsUrl(page));
    updatePagination(data);
    renderReadingsTable(normalizeReadings(data.readings || []));
    setText("readings-status", "Showing all saved readings.");
  } catch (error) {
    setReadingsTableMessage("Could not load readings.");
    setText("readings-status", "Could not load saved readings.");
  }
}

document.querySelectorAll(".sort-button").forEach((button) => {
  button.addEventListener("click", () => setSort(button.dataset.sortBy));
});
loadReadings();
setInterval(loadReadings, 60000);
