/**
 * Renders the RuneLite "Copy Banktag Loadout" string (emitted into the page
 * by main.py's banktags() macro) as a visual bank-interface grid.
 *
 * Hidden by default and built lazily on first reveal - via the "Show Bank
 * View" toggle, or automatically if it was left open on a previous page
 * (tracked in localStorage, so it survives the maxed/unmaxed toggle too,
 * since that's just a normal same-origin navigation).
 *
 * The loadout string only carries item IDs, so names/icons come from small
 * same-origin files main.py generates at build time (see
 * generate_bank_item_names()/generate_bank_item_icons()) instead of every
 * visitor's browser hitting the OSRS Wiki / chisel.weirdgloop.org live -
 * same approach github.com/JZomDev/BankLayoutViewer takes for its whole
 * catalogue.
 *  - Icons: data/icons/<id>.png, falling back to chisel's live sprite URL
 *    if the local one 404s. ID-keyed rather than name-keyed: a name-based
 *    URL 404s for charge-count variants and stackable-currency pile icons,
 *    and misses untradeable items entirely.
 *  - Names (hover title): data/item-names.json. Links point at the wiki -
 *    the item's page when a name resolves, otherwise
 *    Special:Lookup?type=item&id=<id>.
 *
 * Cells have no per-slot background of their own - the real bank interface
 * doesn't box in individual slots, items just sit on the plain wood panel
 * (.equipment in stylesheets/extra.css).
 *
 * Accessibility: toggle keeps aria-expanded in sync, empty cells are
 * aria-hidden, multiple loadouts use tablist/tab/tabpanel roles. A
 * "Loading…" placeholder covers the gap before the mapping fetch resolves.
 *
 * Works on any bank tag page generically: looks for
 *   <div class="bank-view" data-source="ID_OF_HIDDEN_TEXTAREA" hidden></div>
 * paired with #bank-view-toggle, reading the loadout string from that
 * textarea. No per-tier JS needed.
 */
(function () {
  const WIKI = "https://oldschool.runescape.wiki";
  // Relative: only ever used from a /bank/<tier>/ page, so this always
  // resolves to <site-root>/bank/data/... regardless of where the site is hosted.
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
          // A dedicated, unsigned placeholder item ID - not the real item's
          // ID negated the way RuneLite's internal layout storage does it
          // (this clipboard format doesn't), so can't be recognized from
          // the number's sign alone (see the check below).
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
        // slotIndex -> itemId. A negative ID would be a placeholder, but
        // this format doesn't emit those - see loadMapping() for the ID
        // scheme it actually uses.
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

        // Keyed by ID, so it renders even when the name lookup below misses
        // (untradeable items aren't in the price API's mapping).
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
          // Local icon missing - try the live sprite once before giving up.
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

  // Remembers open/closed state across page views (localStorage carries
  // across the maxed/unmaxed toggle too - same-origin navigation). Wrapped
  // in try/catch: storage can throw in private browsing, and this is a
  // nice-to-have, not worth breaking the bank view over.
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
          // renderInto() clears this once the mapping's ready - shows
          // something immediately rather than leaving the panel looking
          // unresponsive on a slow connection.
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

  // document$ fires on every mkdocs-material instant-navigation render
  // (including the first) - use only one listener source, or first load
  // double-inits and the toggle becomes a no-op.
  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
