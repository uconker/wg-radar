const MAX_MINUTES_SCALE = 60; // matches config.MAX_TRANSIT_MINUTES on the backend

let allListings = [];

const listingsEl = document.getElementById("listings");
const updatedAtEl = document.getElementById("updated-at");
const template = document.getElementById("listing-card-template");

const minutesFilter = document.getElementById("minutes-filter");
const minutesFilterValue = document.getElementById("minutes-filter-value");
const priceFilter = document.getElementById("price-filter");
const priceFilterValue = document.getElementById("price-filter-value");
const sortSelect = document.getElementById("sort-select");

function formatUpdatedAt(iso) {
  if (!iso) return "never yet — waiting on the first run";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function render() {
  const maxMinutes = Number(minutesFilter.value);
  const maxPrice = Number(priceFilter.value);
  const sortBy = sortSelect.value;

  let filtered = allListings.filter(
    (l) => l.transit_minutes <= maxMinutes && (l.price_eur == null || l.price_eur <= maxPrice)
  );

  if (sortBy === "transit") {
    filtered.sort((a, b) => a.transit_minutes - b.transit_minutes);
  } else if (sortBy === "price") {
    filtered.sort((a, b) => (a.price_eur ?? Infinity) - (b.price_eur ?? Infinity));
  } else if (sortBy === "recent") {
    filtered.sort((a, b) => new Date(b.added_at) - new Date(a.added_at));
  }

  listingsEl.innerHTML = "";

  if (filtered.length === 0) {
    const p = document.createElement("p");
    p.className = "empty-state";
    p.textContent = allListings.length === 0
      ? "No listings yet. Once the first scheduled run has processed an alert email, matches will show up here."
      : "Nothing matches the current filters — try widening them.";
    listingsEl.appendChild(p);
    return;
  }

  for (const listing of filtered) {
    const node = template.content.cloneNode(true);
    node.querySelector(".card__time-value").textContent = listing.transit_minutes;
    node.querySelector(".card__time-bar-fill").style.width =
      `${Math.min(100, (listing.transit_minutes / MAX_MINUTES_SCALE) * 100)}%`;
    node.querySelector(".card__title").textContent = listing.title;
    node.querySelector(".card__town").textContent = listing.town;
    node.querySelector(".card__price").textContent =
      listing.price_eur != null ? `${listing.price_eur} €` : "price not parsed";
    const link = node.querySelector(".card__link");
    link.href = listing.url;
    listingsEl.appendChild(node);
  }
}

minutesFilter.addEventListener("input", () => {
  minutesFilterValue.textContent = `${minutesFilter.value} min`;
  render();
});
priceFilter.addEventListener("input", () => {
  priceFilterValue.textContent = `${priceFilter.value} €`;
  render();
});
sortSelect.addEventListener("change", render);

fetch("data/listings.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((data) => {
    allListings = data.listings || [];
    updatedAtEl.textContent = formatUpdatedAt(data.updated_at);
    render();
  })
  .catch(() => {
    listingsEl.innerHTML = '<p class="empty-state">Could not load data/listings.json.</p>';
  });
