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

async function loadDashboard() {
  let location = DEFAULT_LOCATION;

  try {
    const latest = await fetchJson("/api/readings/latest");
    location = latest.location || DEFAULT_LOCATION;
    setText("location", location);

    if (latest.reading) {
      setText("indoor-temp", formatTemp(latest.reading.inside_temp_f));
      setText("indoor-humidity", formatPercent(latest.reading.inside_humidity));
      setText("outdoor-temp", formatTemp(latest.reading.outside_temp_f));
      setText("outdoor-note", "From latest saved reading");
      setText("status", `Latest sensor update: ${new Date(latest.reading.recorded_at).toLocaleString()}`);
    } else {
      setText("indoor-temp", "--");
      setText("indoor-humidity", "--");
      setText("status", "No indoor readings saved yet.");
    }
  } catch (error) {
    setText("location", location);
    setText("status", "Could not load saved readings.");
  }

  try {
    const weather = await fetchJson(`/api/outdoor/current?location=${encodeURIComponent(location)}`);
    setText("location", weather.location || location);
    setText("outdoor-temp", formatTemp(weather.temperature));
    setText("outdoor-note", "Live outdoor weather");
  } catch (error) {
    setText("outdoor-note", "Outdoor weather unavailable");
  }
}

updateClock();
setInterval(updateClock, 1000);
loadDashboard();
setInterval(loadDashboard, 60000);
