/**
 * Renders the RuneLite "Copy Banktag Loadout" string (already emitted into the
 * page by the `banktags()` macro in main.py) as a visual bank-interface grid.
 *
 * The loadout string only carries item IDs, not names, so two lookups happen
 * once per page load:
 *  - Icons come straight from chisel.weirdgloop.org's sprite server, keyed by
 *    item ID (https://chisel.weirdgloop.org/static/img/osrs-sprite/<id>.png).
 *    That's deliberate, not a shortcut: building the URL from an item's
 *    *name* the way item_render() does in main.py (oldschool.runescape.wiki
 *    /images/<Name>.png) 404s for a meaningful slice of real bank items -
 *    charge-count variants like "Necklace of passage(5)" whose icon file
 *    doesn't share the base item's name, stackable currencies like "Revenant
 *    ether" that only have pile-size icons ("Revenant_ether_1.png"), and
 *    items the wiki has since renamed. The ID-keyed sprite endpoint (same
 *    Weird Gloop org as the wiki/prices API, sourced from the game's own
 *    item cache) sidesteps all of that and also covers untradeable items the
 *    price API doesn't know about at all.
 *  - Names (for the hover title and the click-through link) still come from
 *    the OSRS Wiki's public price-mapping endpoint, since that's only used
 *    for tradeable items and isn't as failure-prone for that purpose.
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
  const SPRITE_URL = "https://chisel.weirdgloop.org/static/img/osrs-sprite";
  const LOOKUP_URL = "https://chisel.weirdgloop.org/moid/item_id.html";
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

  function iconUrl(id) {
    return `${SPRITE_URL}/${id}.png`;
  }
  function pageUrl(name) {
    return `${WIKI}/w/${name.replace(/ /g, "_")}`;
  }
  function lookupUrl(id) {
    return `${LOOKUP_URL}#${id}`;
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

        // The sprite is keyed by ID, so it renders regardless of whether the
        // name lookup below succeeds (untradeable items aren't in the price
        // API's mapping, but still have a real icon).
        const name = itemMap.get(id);
        const a = document.createElement("a");
        a.href = name ? pageUrl(name) : lookupUrl(id);
        a.title = name || "Item #" + id;
        a.target = "_blank";
        a.rel = "noopener";
        const img = document.createElement("img");
        img.loading = "lazy";
        img.src = iconUrl(id);
        img.alt = name || "Item #" + id;
        img.onerror = () => {
          a.remove();
          cell.textContent = id;
          cell.title = "Item #" + id;
        };
        a.appendChild(img);
        cell.appendChild(a);
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
