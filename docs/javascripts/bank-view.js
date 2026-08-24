/**
 * Renders the RuneLite "Copy Banktag Loadout" string (already emitted into the
 * page by the `banktags()` macro in main.py) as a visual bank-interface grid.
 *
 * The bank view starts hidden by default and is built lazily the first time
 * it's revealed, so a page view that never opens it never costs a mapping
 * fetch or DOM build. "Revealed" means either clicking the "Show Bank View"
 * button (id="bank-view-toggle"), or - if it was left open on a previous page
 * view anywhere on the site - automatically on load, via a localStorage flag
 * the toggle keeps up to date. That's what makes the open/closed state
 * survive switching the maxed/unmaxed toggle: that's just a normal
 * navigation to a different path on the same origin.
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
 * (see .equipment in stylesheets/extra.css, applied to the whole bank view
 * via the wrapper's class list in main.py).
 *
 * The toggle button keeps aria-expanded in sync, empty cells are marked
 * aria-hidden, and when a tier has more than one saved loadout the tab strip
 * uses the standard tablist/tab/tabpanel ARIA roles. A brief "Loading…"
 * placeholder covers the gap between clicking the toggle and the mapping
 * fetch resolving, so the panel doesn't sit looking inert on a slow
 * connection.
 *
 * Works generically on any bank tag page: it looks for
 *   <div class="bank-view" data-source="ID_OF_HIDDEN_TEXTAREA" hidden></div>
 * paired with a #bank-view-toggle button, and reads the loadout string out
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
        .then((obj) => ({
          names: new Map(Object.entries(obj.names || {}).map(([id, name]) => [Number(id), name])),
          // IDs stored directly in a bank.txt layout that are actually the
          // game's own dedicated "placeholder" cache entry for a real item,
          // not the item itself (e.g. Max cape's placeholder is a distinct
          // ID, not -13280) - RuneLite's own internal layout storage uses a
          // negative sign for this, but the clipboard export format these
          // pages read doesn't, so a placeholder can't be recognized just
          // from the number's sign the way it's checked below.
          placeholderIds: new Set(Object.keys(obj.placeholders || {}).map(Number)),
        }))
        .catch(() => ({ names: new Map(), placeholderIds: new Set() }));
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
        // slotIndex -> itemId. A negative ID is a placeholder (this format
        // never seems to actually emit one in practice - see loadMapping()
        // for the ID that does turn up: a dedicated, unsigned placeholder
        // item ID, distinct from the real item's own ID).
        const slots = new Map();
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

  function buildGrid(loadout, data) {
    const maxSlot = loadout.slots.size ? Math.max(...loadout.slots.keys()) : -1;
    const rows = Math.max(4, Math.ceil((maxSlot + 1) / COLS));
    const grid = document.createElement("div");
    grid.className = "bank-view__grid";

    for (let i = 0; i < rows * COLS; i++) {
      const cell = document.createElement("div");
      cell.className = "bank-view__cell";
      const rawId = loadout.slots.get(i);

      if (rawId === undefined) {
        cell.setAttribute("aria-hidden", "true");
      } else {
        const id = Math.abs(rawId);
        const placeholder = rawId < 0 || data.placeholderIds.has(id);
        if (placeholder) cell.classList.add("bank-view__cell--placeholder");

        // The sprite is keyed by ID, so it renders regardless of whether the
        // name lookup below succeeds (untradeable items aren't in the price
        // API's mapping, but still have a real icon).
        const name = data.names.get(id);
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

  function renderInto(container, loadouts, data) {
    container.innerHTML = "";
    const tabs = document.createElement("div");
    tabs.className = "bank-view__tabs";
    const body = document.createElement("div");
    body.className = "bank-view__body";
    body.id = "bank-view-panel";
    container.appendChild(tabs);
    container.appendChild(body);

    function show(idx) {
      body.innerHTML = "";
      body.appendChild(buildGrid(loadouts[idx], data));
      [...tabs.children].forEach((t, i) => {
        const active = i === idx;
        t.classList.toggle("bank-view__tab--active", active);
        t.setAttribute("aria-selected", active ? "true" : "false");
        if (active) body.setAttribute("aria-labelledby", t.id);
      });
    }

    // Only show tabs when a bank.txt has more than one banktags,... line.
    if (loadouts.length > 1) {
      tabs.setAttribute("role", "tablist");
      body.setAttribute("role", "tabpanel");
      loadouts.forEach((l, idx) => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.id = `bank-view-tab-${idx}`;
        tab.className = "bank-view__tab";
        tab.textContent = l.name;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-controls", body.id);
        tab.addEventListener("click", () => show(idx));
        tabs.appendChild(tab);
      });
    } else {
      tabs.style.display = "none";
    }
    show(0);
  }

  // Remembers whether the bank view was left open, so it comes back open on
  // the next page view - including switching the maxed/unmaxed toggle, which
  // is just a normal navigation to a different path on the same origin, so
  // localStorage carries across it for free. Wrapped in try/catch: storage
  // can throw in private browsing / with site data blocked, and this is a
  // nice-to-have, not something that should ever break the bank view itself.
  const OPEN_STORAGE_KEY = "bank-view-open";
  function getStoredOpenState() {
    try {
      return localStorage.getItem(OPEN_STORAGE_KEY) === "true";
    } catch (e) {
      return false;
    }
  }
  function setStoredOpenState(open) {
    try {
      localStorage.setItem(OPEN_STORAGE_KEY, open ? "true" : "false");
    } catch (e) {
      // ignore
    }
  }

  // The bank view starts hidden (main.py renders it with the `hidden`
  // attribute) and is only built the first time it's revealed, so a page
  // view that never opens it never pays for the mapping fetch or DOM build.
  function wireToggle(container) {
    const toggle = document.getElementById("bank-view-toggle");
    if (!toggle) return;

    let rendered = false;

    function reveal() {
      if (!rendered) {
        rendered = true;
        const source = document.getElementById(container.dataset.source);
        const loadouts = source ? parseLoadouts(source.value || source.textContent || "") : [];
        if (loadouts.length) {
          // renderInto() clears this once the mapping's ready; on a slow
          // connection the mapping fetch (and, once rendered, the icon
          // loads) can take a moment, so show something immediately rather
          // than leaving the panel looking unresponsive after the click.
          container.innerHTML = '<div class="bank-view__loading">Loading…</div>';
          loadMapping().then((data) => renderInto(container, loadouts, data));
        }
      }
      container.hidden = false;
      toggle.textContent = "Hide Bank View";
      toggle.setAttribute("aria-expanded", "true");
    }

    function hide() {
      container.hidden = true;
      toggle.textContent = "Show Bank View";
      toggle.setAttribute("aria-expanded", "false");
    }

    toggle.addEventListener("click", () => {
      const willShow = container.hidden;
      if (willShow) reveal();
      else hide();
      setStoredOpenState(willShow);
    });

    if (getStoredOpenState()) reveal();
  }

  function init() {
    document.querySelectorAll(".bank-view[data-source]").forEach(wireToggle);
  }

  // mkdocs-material's instant-navigation feature swaps page content without a
  // full reload; document$ fires on every page render (including the first),
  // so when it's present it's the only listener wired up - subscribing to it
  // *and* DOMContentLoaded would double-init on first load, attaching two
  // click listeners to the same toggle button and making it a no-op (each
  // click flips the bank view open then immediately shut again).
  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
