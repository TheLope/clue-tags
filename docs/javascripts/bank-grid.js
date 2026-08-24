/**
 * Renders the RuneLite "Copy Banktag Loadout" string (already emitted into the
 * page by the `banktags()` macro in main.py) as a visual bank-interface grid.
 *
 * The grid starts hidden and is built lazily the first time the "Show Bank
 * Grid" button (id="bank-grid-toggle") is clicked, so viewing the page never
 * costs a mapping fetch or DOM build unless someone actually opens it.
 *
 * The loadout string only carries item IDs, not names, so this pulls from a
 * couple of small same-origin files generated at build time by main.py
 * (generate_bank_item_names() / generate_bank_item_icons()) instead of
 * hitting third-party OSRS Wiki / Weird Gloop infrastructure from every
 * visitor's browser on every page view - see those functions for the "why".
 * In short: this site only ever needs the ~265 item IDs actually used across
 * our fixed set of curated tiers, so it isn't worth every visitor's browser
 * fetching the OSRS Wiki's full ~4,650-item price mapping (for names) or
 * hotlinking chisel.weirdgloop.org's sprite server per icon on every view
 * when that data barely changes and can just be resolved once, ahead of
 * time (the same approach github.com/JZomDev/BankLayoutViewer takes for its
 * whole item catalogue).
 *  - Icons: data/icons/<id>.png, falling back to chisel's live sprite URL if
 *    the local one 404s (e.g. an item added to a bank.txt since the last
 *    build). Both are keyed by ID rather than item name - building the icon
 *    URL from a name the way item_render() does in main.py 404s for a real
 *    slice of items (charge-count variants like "Necklace of passage(5)"
 *    whose icon file doesn't share the base item's name, stackable
 *    currencies that only have pile-size icons, renamed items) and misses
 *    untradeable items entirely; the ID-keyed sprite endpoint sidesteps all
 *    of that.
 *  - Names (for the hover title): data/item-names.json. Click-through links
 *    always point at the wiki (matching item_render() elsewhere on the
 *    site): when a name resolves, straight to its page; otherwise to the
 *    wiki's own Special:Lookup?type=item&id=<id>, which redirects to the
 *    right page for any item, tradeable or not, without needing a name.
 *
 * Cells have no per-slot background of their own - the real OSRS bank
 * interface doesn't box in individual slots the way the equipment/inventory
 * widgets do, it's just items sitting on the plain wood panel background
 * (see .equipment in stylesheets/extra.css, applied to the whole grid via
 * the wrapper's class list in main.py).
 *
 * Works generically on any bank tag page: it looks for
 *   <div class="bank-grid" data-source="ID_OF_HIDDEN_TEXTAREA" hidden></div>
 * paired with a #bank-grid-toggle button, and reads the loadout string out
 * of that textarea. No per-tier JS needed.
 */
(function () {
  const WIKI = "https://oldschool.runescape.wiki";
  // Relative, not absolute: these only ever get used from a /bank/<tier>/
  // page (see data-source usage below), so they always resolve to
  // <site-root>/bank/data/... regardless of where the site itself is hosted.
  const NAMES_URL = "../data/item-names.json";
  const ICONS_URL = "../data/icons";
  const LIVE_SPRITE_URL = "https://chisel.weirdgloop.org/static/img/osrs-sprite";
  const COLS = 8;

  let mappingPromise = null;
  function loadMapping() {
    if (!mappingPromise) {
      mappingPromise = fetch(NAMES_URL)
        .then((r) => r.json())
        .then((obj) => new Map(Object.entries(obj.names || {}).map(([id, name]) => [Number(id), name])))
        .catch(() => new Map());
    }
    return mappingPromise;
  }

  function iconUrl(id) {
    return `${ICONS_URL}/${id}.png`;
  }
  function liveIconUrl(id) {
    return `${LIVE_SPRITE_URL}/${id}.png`;
  }
  function pageUrl(name) {
    return `${WIKI}/w/${name.replace(/ /g, "_")}`;
  }
  function lookupUrl(id) {
    return `${WIKI}/w/Special:Lookup?type=item&id=${id}`;
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
      const cell = document.createElement("div");
      cell.className = "bank-grid__cell";
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
          // Local icon missing (e.g. an item added to a bank.txt since the
          // last build baked docs/bank/data/icons/) - try the live sprite
          // once before giving up on showing an image at all.
          img.onerror = () => {
            a.remove();
            cell.textContent = id;
            cell.title = "Item #" + id;
          };
          img.src = liveIconUrl(id);
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

  // The grid starts hidden (main.py renders it with the `hidden` attribute)
  // and is only built the first time it's revealed, so a page view that
  // never opens it never pays for the mapping fetch or the DOM build.
  function wireToggle(container) {
    const toggle = document.getElementById("bank-grid-toggle");
    if (!toggle) return;

    let rendered = false;

    toggle.addEventListener("click", () => {
      const willShow = container.hidden;

      if (willShow && !rendered) {
        rendered = true;
        const source = document.getElementById(container.dataset.source);
        const loadouts = source ? parseLoadouts(source.value || source.textContent || "") : [];
        if (loadouts.length) {
          loadMapping().then((itemMap) => renderInto(container, loadouts, itemMap));
        }
      }

      container.hidden = !willShow;
      toggle.textContent = willShow ? "Hide Bank Grid" : "Show Bank Grid";
    });
  }

  function init() {
    document.querySelectorAll(".bank-grid[data-source]").forEach(wireToggle);
  }

  // mkdocs-material's instant-navigation feature swaps page content without a
  // full reload; document$ fires on every page render (including the first),
  // so when it's present it's the only listener wired up - subscribing to it
  // *and* DOMContentLoaded would double-init on first load, attaching two
  // click listeners to the same toggle button and making it a no-op (each
  // click flips the grid open then immediately shut again).
  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
