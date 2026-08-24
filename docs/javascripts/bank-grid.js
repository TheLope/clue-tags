/**
 * Renders the RuneLite "Copy Banktag Loadout" string (already emitted into the
 * page by the `banktags()` macro in main.py) as a visual bank-interface grid.
 *
 * Item icons are resolved the same way item_render() in main.py does:
 *   https://oldschool.runescape.wiki/images/<Item_Name_With_Underscores>.png
 * The loadout string only carries item IDs, so we resolve id -> name once per
 * page load via the OSRS Wiki's public price-mapping endpoint, then build the
 * URL with that same convention.
 *
 * Each cell reuses the site's existing .equipment-blank slot art (see
 * stylesheets/extra.css) so the grid matches the equipment/inventory widgets
 * instead of introducing new slot artwork.
 *
 * Works generically on any bank tag page: it looks for
 *   <div class="bank-grid" data-source="ID_OF_HIDDEN_TEXTAREA"></div>
 * and reads the loadout string out of that textarea. No per-tier JS needed.
 */
(function () {
  const WIKI = "https://oldschool.runescape.wiki";
  const MAPPING_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping";
  const COLS = 8;

  let mappingPromise = null;
  function loadMapping() {
    if (!mappingPromise) {
      mappingPromise = fetch(MAPPING_URL)
        .then((r) => r.json())
        .then((list) => new Map(list.map((i) => [i.id, i.name])))
        .catch(() => new Map());
    }
    return mappingPromise;
  }

  function wikiName(name) {
    return name.replace(/ /g, "_");
  }
  function iconUrl(name) {
    return `${WIKI}/images/${wikiName(name)}.png`;
  }
  function pageUrl(name) {
    return `${WIKI}/w/${wikiName(name)}`;
  }

  // One or more "banktags,1,NAME,item,item,...,layout,slot,id,slot,id,..." lines.
  function parseLoadouts(raw) {
    return raw
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.startsWith("banktags"))
      .map((line) => {
        const parts = line.split(",");
        const name = parts[2];
        const layoutIdx = parts.indexOf("layout");
        const slots = new Map(); // slotIndex -> itemId (negative = placeholder)
        if (layoutIdx !== -1) {
          for (let i = layoutIdx + 1; i < parts.length; i += 2) {
            const slot = parseInt(parts[i], 10);
            const itemId = parseInt(parts[i + 1], 10);
            if (!Number.isNaN(slot) && !Number.isNaN(itemId)) slots.set(slot, itemId);
          }
        }
        return { name, slots };
      });
  }

  function buildGrid(loadout, itemMap) {
    const maxSlot = loadout.slots.size ? Math.max(...loadout.slots.keys()) : -1;
    const rows = Math.max(4, Math.ceil((maxSlot + 1) / COLS));
    const grid = document.createElement("div");
    grid.className = "bank-grid__grid";

    for (let i = 0; i < rows * COLS; i++) {
      // .equipment-blank supplies the site's standard slot art/size; every
      // cell gets it, matching how a bank interface always shows a slot
      // outline whether or not it holds an item.
      const cell = document.createElement("div");
      cell.className = "bank-grid__cell equipment-blank";
      const rawId = loadout.slots.get(i);

      if (rawId !== undefined) {
        const placeholder = rawId < 0;
        const id = Math.abs(rawId);
        if (placeholder) cell.classList.add("bank-grid__cell--placeholder");

        const name = itemMap.get(id);
        if (name) {
          const a = document.createElement("a");
          a.href = pageUrl(name);
          a.title = name;
          a.target = "_blank";
          a.rel = "noopener";
          const img = document.createElement("img");
          img.loading = "lazy";
          img.src = iconUrl(name);
          img.alt = name;
          img.onerror = () => {
            img.remove();
            cell.textContent = id;
          };
          a.appendChild(img);
          cell.appendChild(a);
        } else {
          cell.textContent = id;
          cell.title = "Item #" + id;
        }
      }
      grid.appendChild(cell);
    }
    return grid;
  }

  function renderInto(container, loadouts, itemMap) {
    container.innerHTML = "";
    const tabs = document.createElement("div");
    tabs.className = "bank-grid__tabs";
    const body = document.createElement("div");
    body.className = "bank-grid__body";
    container.appendChild(tabs);
    container.appendChild(body);

    function show(idx) {
      body.innerHTML = "";
      body.appendChild(buildGrid(loadouts[idx], itemMap));
      [...tabs.children].forEach((t, i) =>
        t.classList.toggle("bank-grid__tab--active", i === idx)
      );
    }

    // Only show tabs when a bank.txt has more than one banktags,... line.
    if (loadouts.length > 1) {
      loadouts.forEach((l, idx) => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = "bank-grid__tab";
        tab.textContent = l.name;
        tab.addEventListener("click", () => show(idx));
        tabs.appendChild(tab);
      });
    } else {
      tabs.style.display = "none";
    }
    show(0);
  }

  function init() {
    const containers = document.querySelectorAll(".bank-grid[data-source]");
    if (!containers.length) return;

    loadMapping().then((itemMap) => {
      containers.forEach((container) => {
        const source = document.getElementById(container.dataset.source);
        if (!source) return;
        const loadouts = parseLoadouts(source.value || source.textContent || "");
        if (!loadouts.length) return;
        renderInto(container, loadouts, itemMap);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // mkdocs-material's instant-navigation feature swaps page content without a
  // full reload; document$ fires on every page render so the grid still shows
  // up when navigating between tiers via the nav sidebar.
  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  }
})();
