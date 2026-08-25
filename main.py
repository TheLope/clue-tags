"""
mkdocs-macros hook for this site (see define_env() below), plus the
build-time data pipeline behind two features:
  - bank-view (docs/javascripts/bank-view.js): the visual grid rendering of
    a saved RuneLite bank tag loadout on bank tag pages.
  - the equipment/inventory/rune-pouch/spellbook diagrams also shown on
    those pages, built from docs/bank/data/*.yml via item_render().

Both need OSRS item IDs/names resolved into icons and display names without
every visitor's browser hitting the OSRS Wiki or chisel.weirdgloop.org live
for it - see fetch_infobox_items(). Generated files:

  docs/bank/data/item-names.json      id -> name, for bank-view. Gitignored;
                                       regenerated when the tracked ID set
                                       changes or the file is older than
                                       NAMES_STALE_AFTER_SECONDS.

  docs/bank/data/icons/<id>.png       One icon per item ID used by
                                       bank-view or a diagram. Committed,
                                       unlike the other two - re-fetching
                                       hundreds of files every build would
                                       be expensive, so only missing IDs
                                       get fetched.

  docs/bank/data/diagram-icons.json   name -> item ID, for item_render()'s
                                       diagrams. Gitignored, same staleness
                                       rule as item-names.json.

All three share one crawl of the OSRS Wiki's Bucket API
(fetch_infobox_items()), gated by needs_infobox_crawl().

To force a refresh locally: delete the files above (or specific icons under
docs/bank/data/icons/), then run `mkdocs build`/`mkdocs serve` (needs
network access).
"""

import glob
import json
import os
import re
import shutil
import time
import urllib.parse
import urllib.request

import yaml

NAMES_STALE_AFTER_SECONDS = 30 * 24 * 60 * 60  # 30 days


def collect_bank_item_ids():
    ids = set()
    for path in glob.glob('tags/*/bank.txt'):
        with open(path) as f:
            raw = f.read()
        for line in raw.splitlines():
            parts = line.strip().split(',')
            if not parts or parts[0] != 'banktags' or 'layout' not in parts:
                continue
            layout_idx = parts.index('layout')
            for i in range(layout_idx + 1, len(parts) - 1, 2):
                try:
                    ids.add(abs(int(parts[i + 1])))
                except ValueError:
                    continue
    return ids


def collect_diagram_item_names():
    """
    Every unique item name referenced in docs/bank/data/*.yml, for
    item_render()'s diagrams. Read directly rather than via env.variables,
    same as collect_bank_item_ids() - self-contained, not dependent on
    mkdocs-macros' plugin load order.
    """
    names = set()
    for path in glob.glob('docs/bank/data/*.yml'):
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        for tier_data in data.values():
            for name in (tier_data.get('equipment') or {}).values():
                if name and name != '~':
                    names.add(name)
            for row in tier_data.get('inventory') or []:
                for item in row:
                    if not item:
                        continue
                    # strip a "/quantity" suffix, e.g. "Aether rune/1025" - same as inventory_td()
                    names.add(item.split('/')[0] if '/' in item else item)
            for name in tier_data.get('spellbook') or []:
                if name:
                    names.add(name)
            for name in tier_data.get('rune_pouch') or []:
                if name:
                    names.add(name)
    return names


def _preferred_image(name, images):
    """
    Picks which image in an infobox row's list to use for `name`. Prefers
    the last entry only when every entry matches "<name> <number>.png" (a
    genuine size/pile-tier series); otherwise falls back to the first entry
    (infobox convention's primary image).
    """
    if not images:
        return None
    if len(images) == 1:
        return images[0]

    tier_pattern = re.compile(re.escape(name) + r' \d+\.png$', re.IGNORECASE)
    if all(tier_pattern.match(image) for image in images):
        return images[-1]
    return images[0]


def fetch_infobox_items():
    """
    Crawls the OSRS Wiki's Bucket API (infobox_item bucket) for
    item_id -> {name, image}, paginated 500 rows at a time (~28 requests).
    The query language has no IN/array filter, so a full crawl filtered
    locally beats one request per ID.

    Covers untradeable items too (quest rewards, currencies, cosmetics),
    unlike the price-mapping API. Category exclusions mirror
    github.com/JZomDev/BankLayoutViewer's own generation script (skips
    interface elements, unobtainable/beta/discontinued content).

    See _preferred_image() for how `image` gets picked.
    """
    items = {}
    offset = 0
    while True:
        query = (
            "bucket('infobox_item').select('item_id','item_name','image')"
            ".where('Category:Items')"
            ".where('item_id', '!=', bucket.Null())"
            ".where('item_name', '!=', bucket.Null())"
            ".where(bucket.Not('Category:Interface items'))"
            ".where(bucket.Not('Category:Unobtainable items'))"
            ".where(bucket.Not('Category:Pages using information from game APIs or cache'))"
            ".where(bucket.Not('Category:Discontinued content'))"
            ".where(bucket.Not('Category:Beta items'))"
            f".limit(500).offset({offset}).run()"
        )
        params = urllib.parse.urlencode({'action': 'bucket', 'format': 'json', 'query': query})
        request = urllib.request.Request(
            f'https://oldschool.runescape.wiki/api.php?{params}',
            headers={'User-Agent': 'clue-tags bank-view item data cache (https://github.com/TheLope/clue-tags)'},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read())
        if 'error' in data:
            raise RuntimeError(f'bucket query error: {data["error"]}')

        rows = data.get('bucket', [])
        for row in rows:
            item_ids = row.get('item_id')
            item_name = row.get('item_name')
            if not item_ids or not item_name:
                continue
            try:
                item_id = int(item_ids[0])
            except (ValueError, TypeError):
                continue
            images = [i.removeprefix('File:') for i in (row.get('image') or [])]
            image = _preferred_image(item_name, images)
            items[item_id] = {'name': item_name, 'image': image}

        if len(rows) < 500:
            break
        offset += 500

    return items


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _cache_is_fresh(existing, keys):
    """
    Fresh means present, generated for exactly this set of keys (item IDs
    or item names), and not older than NAMES_STALE_AFTER_SECONDS.
    """
    if existing is None or existing.get('keys') != keys:
        return False
    age = time.time() - existing.get('generated_at', 0)
    return age < NAMES_STALE_AFTER_SECONDS


def _coverage_regressed(old_count, new_count):
    """
    True if a fresh crawl resolved meaningfully fewer items than the
    existing cache (more than a 10% drop) - catches the wiki's Bucket
    schema/category structure shifting under us and the crawl "succeeding"
    but only partially, which would otherwise silently degrade coverage
    build over build.
    """
    return old_count > 0 and new_count < old_count * 0.9


def resolve_placeholder_ids(ids):
    """
    Some IDs that can end up in tags/*/bank.txt aren't real items - they're
    the game's own placeholder cache entry for one (e.g. Max cape 13280's
    placeholder is a distinct 14281, configName "placeholder_skillcape_max").
    RuneLite's *internal* layout storage negates the real ID for this (see
    LayoutManager.java upstream), but the "Copy Banktag Loadout" clipboard
    format doesn't - the placeholder's own unsigned ID is what would show up
    directly in a bank.txt layout.

    The Bucket API doesn't know about placeholders, so this fetches
    chisel.weirdgloop.org's full item cache dump (~11MB) instead - only
    called when the normal infobox crawl leaves IDs unresolved.

    Returns {placeholder_id: real_item_id} for whichever of `ids` are
    placeholders.
    """
    request = urllib.request.Request(
        'https://chisel.weirdgloop.org/moid/data_files/itemsmin.js',
        headers={'User-Agent': 'clue-tags bank-view placeholder item cache (https://github.com/TheLope/clue-tags)'},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read().decode('utf-8')
    data = json.loads(content[content.index('['):])

    wanted = set(ids)
    placeholders = {}
    for item in data:
        item_id = item.get('id')
        if item_id not in wanted:
            continue
        real_id = item.get('placeholderId')
        if (item.get('configName') or '').startswith('placeholder_') and isinstance(real_id, int) and real_id >= 0:
            placeholders[item_id] = real_id
    return placeholders


def generate_bank_item_names(ids, infobox_items):
    """
    Resolves item names for bank-view's tracked item IDs once at build time
    into a same-origin file, instead of every visitor's browser fetching
    wiki data live. `infobox_items` comes from fetch_infobox_items(), shared
    with generate_bank_item_icons()/generate_diagram_item_ids() - see
    needs_infobox_crawl().

    Skips rewriting unless the ID set changed or the file is stale (see
    _cache_is_fresh()) - otherwise every `mkdocs serve` rebuild would
    rewrite a file the dev server watches for live-reload, causing an
    infinite reload loop.

    IDs the crawl couldn't name get one more attempt via
    resolve_placeholder_ids(): the real item's name goes into `names`, and
    the mapping is also stored under "placeholders" so bank-view.js can mark
    them and generate_bank_item_icons() can reuse the real item's icon.
    """
    out_path = 'docs/bank/data/item-names.json'
    ids_key = sorted(ids)
    existing = _read_json(out_path)

    if _cache_is_fresh(existing, ids_key):
        return

    if infobox_items:
        names = {str(i): infobox_items[i]['name'] for i in ids if i in infobox_items}
    elif existing is not None:
        return  # crawl failed or wasn't needed for this reason - keep the previous file
    else:
        names = {}

    placeholders = {}
    still_missing = {i for i in ids if str(i) not in names}
    if still_missing:
        try:
            resolved = resolve_placeholder_ids(still_missing)
        except Exception as e:
            print(f'[bank-view] warning: could not resolve placeholder items ({e})')
            resolved = {}
        for placeholder_id, real_id in resolved.items():
            real_name = (infobox_items.get(real_id) or {}).get('name')
            if real_name:
                names[str(placeholder_id)] = real_name
                placeholders[str(placeholder_id)] = real_id

    # Compared after placeholder resolution: `existing` already includes any
    # placeholders resolved last time, so comparing before would trip this
    # guard on every build.
    if existing is not None and _coverage_regressed(len(existing.get('names', {})), len(names)):
        print(
            f'[bank-view] warning: item name coverage dropped from {len(existing["names"])} '
            f'to {len(names)} resolved - keeping previous item-names.json '
            '(possible wiki API change?)'
        )
        return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({'keys': ids_key, 'names': names, 'placeholders': placeholders, 'generated_at': time.time()}, f)


def generate_bank_item_icons(ids, infobox_items):
    """
    Self-hosts one icon per item ID instead of hotlinking a live sprite
    server per visitor - same idea as generate_bank_item_names(). Shared
    between bank-view and the diagrams (define_env() passes the union of
    both ID sets), so an item referenced by both only downloads once.

    Inspired by github.com/JZomDev/BankLayoutViewer, which does this for its
    entire ~12,600-item catalogue since it accepts arbitrary user-pasted
    loadouts; this site only needs the IDs actually used across its fixed
    tiers/diagrams, so it stays well under a megabyte.

    Prefers the wiki's own image via Special:Filepath (resolves
    renames/redirects, same as BankLayoutViewer's own downloader), falling
    back to chisel.weirdgloop.org's ID-keyed sprite server when no infobox
    image is available - see bank-view.js for why ID-keyed matters
    (name-based wiki URLs 404 for a real slice of items).

    Committed to the repo, unlike item-names.json: icons rarely change, so
    already-downloaded ones are left in place and only newly referenced IDs
    get fetched. bank-view.js and item_render() each have their own
    client-side fallback if a specific icon is still missing locally.
    """
    out_dir = 'docs/bank/data/icons'
    os.makedirs(out_dir, exist_ok=True)
    headers = {'User-Agent': 'clue-tags bank-view icon cache (https://github.com/TheLope/clue-tags)'}
    fetched, skipped, failed = 0, 0, 0

    for item_id in sorted(ids):
        out_path = f'{out_dir}/{item_id}.png'
        if os.path.exists(out_path):
            skipped += 1
            continue

        image = (infobox_items.get(item_id) or {}).get('image')
        urls = []
        if image:
            urls.append(f'https://oldschool.runescape.wiki/w/Special:Filepath/{image.replace(" ", "_")}')
        urls.append(f'https://chisel.weirdgloop.org/static/img/osrs-sprite/{item_id}.png')

        saved = False
        last_error = None
        for url in urls:
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=10) as response:
                    content = response.read()
                with open(out_path, 'wb') as f:
                    f.write(content)
                saved = True
                break
            except Exception as e:
                last_error = e
        if saved:
            fetched += 1
        else:
            print(f'[bank-view] warning: could not fetch icon for item {item_id} ({last_error})')
            failed += 1

    if fetched or failed:
        print(f'[bank-view] icons: {fetched} fetched, {skipped} already cached, {failed} failed')


def generate_diagram_item_ids(names, infobox_items):
    """
    item_render() built its icon URL from the item's display name the same
    naive way bank-view originally did - 404s or a wrong icon for the same
    classes of item generate_bank_item_icons() works around. Resolves each
    name to an item ID here instead, from the same shared infobox crawl, so
    item_render() can point at the same self-hosted
    docs/bank/data/icons/<id>.png files bank-view downloads.

    A name can have more than one infobox row behind it (e.g. a plain
    "Blood rune" vs. a separate "Blood rune" used only in the Barbarian
    Assault shop's own UI) - the row whose image is the plain "<name>.png"
    wins over one with an extra qualifier like "(Barbarian Assault)".

    Matching is case-insensitive: docs/bank/data/*.yml is hand-typed and
    doesn't always match the wiki's own capitalization exactly. Three more
    rules cover cases an exact match still misses:
      - A bare name (no parenthetical qualifier of our own) with a
        charge-count series prefers the *highest* charge over the bare
        infobox entry, even when that entry technically matches - it can
        represent the *uncharged* state instead (Combat bracelet, Ring of
        wealth, Skills necklace), and some names (Burning amulet, Necklace
        of passage) have no bare entry at all.
      - An explicit qualifier we typed ourselves is honored exactly, not
        overridden by the rule above - e.g. "Pharaoh's sceptre (uncharged)"
        has its own exact infobox entry.
      - Failing an exact match, our name may carry a qualifier the wiki's
        item_name doesn't (e.g. "Catherby teleport (tablet)" vs. the wiki's
        "Catherby teleport") - strip a trailing "(...)" and retry.
    Names with no match by any of these keep the old live-hotlink fallback
    in item_render(), so this can only fix an icon, never break one.
    """
    out_path = 'docs/bank/data/diagram-icons.json'
    names_key = sorted(names)
    existing = _read_json(out_path)

    if _cache_is_fresh(existing, names_key):
        return

    if infobox_items:
        by_name = {}  # lowercase name -> (item_id, image)
        by_charge_base = {}  # lowercase base name -> [(charge_num, item_id)]
        charge_pattern = re.compile(r'^(.*?)\s*\((\d+)\)$')
        for item_id, item in infobox_items.items():
            if not item['image']:
                continue
            key = item['name'].lower()
            is_default = item['image'].lower() == f"{item['name']}.png".lower()
            current = by_name.get(key)
            current_is_default = current is not None and current[1].lower() == f"{item['name']}.png".lower()
            if current is None or (is_default and not current_is_default):
                by_name[key] = (item_id, item['image'])

            charge_match = charge_pattern.match(item['name'])
            if charge_match:
                base_key = charge_match.group(1).lower()
                by_charge_base.setdefault(base_key, []).append((int(charge_match.group(2)), item_id))

        def resolve(name):
            key = name.lower()

            # Bare name: prefer a charge-count series over the bare infobox
            # entry, if one exists - the bare entry is often the *uncharged*
            # look instead (see docstring above).
            if '(' not in name:
                variants = by_charge_base.get(key)
                if variants:
                    return max(variants, key=lambda v: v[0])[1]

            if key in by_name:
                return by_name[key][0]

            # Our name may carry a qualifier the wiki's item_name doesn't
            # (e.g. "Catherby teleport (tablet)" vs. the wiki's "Catherby
            # teleport"). Doesn't fall through to the charge-count
            # preference above - an explicit qualifier we typed, like
            # "(uncharged)", should be honored exactly.
            stripped = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip().lower()
            if stripped and stripped != key and stripped in by_name:
                return by_name[stripped][0]

            return None

        item_ids = {}
        for name in names:
            item_id = resolve(name)
            if item_id is not None:
                item_ids[name] = item_id
    elif existing is not None:
        return  # crawl failed or wasn't needed for this reason - keep the previous file
    else:
        item_ids = {}

    if existing is not None and _coverage_regressed(len(existing.get('item_ids', {})), len(item_ids)):
        print(
            f'[bank-view] warning: diagram icon coverage dropped from {len(existing["item_ids"])} '
            f'to {len(item_ids)} resolved - keeping previous diagram-icons.json '
            '(possible wiki API change?)'
        )
        return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({'keys': names_key, 'item_ids': item_ids, 'generated_at': time.time()}, f)


def needs_infobox_crawl(bank_ids, diagram_names):
    """
    Whether fetch_infobox_items()'s crawl is worth doing this build: either
    cache is missing/stale (see _cache_is_fresh()), or a bank-view item is
    missing its local icon. Lets define_env() skip the crawl on the common
    case (nothing changed).
    """
    names_fresh = _cache_is_fresh(_read_json('docs/bank/data/item-names.json'), sorted(bank_ids))
    diagram_fresh = _cache_is_fresh(_read_json('docs/bank/data/diagram-icons.json'), sorted(diagram_names))
    icons_missing = any(not os.path.exists(f'docs/bank/data/icons/{i}.png') for i in bank_ids)

    return not names_fresh or not diagram_fresh or icons_missing


def define_env(env):
    """
    Hook function
    """

    bank_item_ids = collect_bank_item_ids()
    diagram_item_names = collect_diagram_item_names()
    infobox_items = {}
    if needs_infobox_crawl(bank_item_ids, diagram_item_names):
        try:
            infobox_items = fetch_infobox_items()
        except Exception as e:
            print(f'[bank-view] warning: could not crawl wiki infobox data ({e})')
    generate_bank_item_names(bank_item_ids, infobox_items)
    generate_diagram_item_ids(diagram_item_names, infobox_items)
    diagram_item_ids = (_read_json('docs/bank/data/diagram-icons.json') or {}).get('item_ids', {})
    placeholder_real_ids = {
        int(k): v for k, v in (_read_json('docs/bank/data/item-names.json') or {}).get('placeholders', {}).items()
    }

    # Shared icon store: an item referenced by bank-view, a diagram, or as
    # the real item behind a placeholder ID only gets downloaded once.
    generate_bank_item_icons(
        bank_item_ids | set(diagram_item_ids.values()) | set(placeholder_real_ids.values()), infobox_items
    )

    # Placeholder IDs reuse the real item's icon under their own filename,
    # so bank-view.js's ID-keyed lookup works for them unmodified. Always
    # overwrites: generate_bank_item_icons()'s own chisel fallback can fetch
    # a mismatched icon directly for a placeholder ID (no infobox image to
    # go on) - this copy is a cheap local file write, so there's no reason
    # to trust a possibly-stale existing file over it.
    for placeholder_id, real_id in placeholder_real_ids.items():
        src = f'docs/bank/data/icons/{real_id}.png'
        dst = f'docs/bank/data/icons/{placeholder_id}.png'
        if os.path.exists(src):
            shutil.copyfile(src, dst)

    wiki_url = 'https://oldschool.runescape.wiki'

    @env.macro
    def index_link(tier):
        image = 'Mimic' if tier == 'mimic' else f'Clue_scroll_({ tier })'

        return f"""
                <a href="{ tier }">
                    <div style="width: 85px !important; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-bottom:10px">
                        <img style="vertical-align:middle" src="{ wiki_url }/images/{ image }_detail.png" width="35">
                        <span>{ tier.title() }</span>
                    </div>
                </a>
                """

    def item_render(item):
        # Prefer the self-hosted icon when resolved for this name (see
        # generate_diagram_item_ids()); onerror falls back to the live
        # hotlink if the local file is missing (e.g. a name added since the
        # last build) or was never resolved.
        item_id = diagram_item_ids.get(item)
        live_url = f"{ wiki_url }/images/{ item.replace(' ', '_') }.png"

        if item_id is not None:
            src = f"../data/icons/{ item_id }.png"
            onerror = f" onerror=\"this.onerror=null;this.src='{ live_url }'\""
        else:
            src = live_url
            onerror = ""

        return f"""
                <a href="{ wiki_url }/w/{ item.replace(' ', '_') }"
                    title="{ item }">
                    <img src="{ src }"{ onerror }>
                </a>
                """

    def equipment_div(d, slot):
        item = d['equipment'][slot]

        return f"""
                <div class="equipment-{ slot } {'equipment-blank' if item else ''}">
                    <div class="equipment-plinkp">
                        { item_render(item) if item else ''}
                    </div>
                </div>
                """

    @env.macro
    def equipment(tier):
        r = ''

        for slot in ['head','cape','neck','ammo','ammo2','weapon','torso','legs','shield','gloves','boots','ring']:
            r += equipment_div(env.variables[tier], slot)

        return r

    def inventory_td(item):
        quantity = None

        if item and '/' in item:
            item, quantity = item.split('/')

        return f"""
                <td>
                    { item_render(item) if item else ''}
                    { f'<span class="inv-quantity-text qty-1">{ quantity }' if quantity else ''}
                </td>
                """

    @env.macro
    def inventory(tier):
        r = '<tr>'

        for row in env.variables[tier]['inventory']:
            for index in range(len(row)):
                r += inventory_td(row[index])
            r += '</tr><tr>'

        return r + '</tr>'

    @env.macro
    def spellbook(tier):
        spells = env.variables[tier]['spellbook']

        if not spells:
            return ''

        r = f"""
            <table class="spellstable storage-center">
                <tbody>
                    <tr>
            """

        for index in range(len(spells)):
            middle = index > 0
            r += rune_pouch_td(spells, index, middle)

        return r + """
                           </tr>
                       </tbody>
                   </table>
                   """

    def rune_pouch_td(runes, index, middle):
        return f"""
                    <td {'class="middle-rune"' if middle else ''}>
                    { item_render(runes[index]) }
                </td>
                """

    @env.macro
    def rune_pouch(tier):
        runes = env.variables[tier]['rune_pouch']

        if not runes:
            return ''

        r = f"""
            <table class="runepouchtable storage-center {'divinerunepouch' if len(runes) == 4 else ''}">
                <tbody>
                    <tr>
            """

        for index in range(len(runes)):
            middle = index in [1, 2]
            r += rune_pouch_td(runes, index, middle)

        return r + """
                           </tr>
                       </tbody>
                   </table>
                   """

    @env.macro
    def banktags(tier):
        with open(f'tags/{ tier }/bank.txt') as f: tags = f.read()

        return f"""
<td colspan="2">
    <textarea id="banktags" style="display:none;">
        { tags }
    </textarea>
    <div class="tooltip">
        <button id="copy" type="button" class="equipment">
            <span id="copyTooltip" class="tooltiptext">Copy to clipboard</span>
            Copy Banktag Loadout
        </button>
    </div>
    <button id="bank-view-toggle" type="button" class="equipment" aria-expanded="false" aria-controls="bank-view">Show Bank View</button>
    <div id="bank-view" class="bank-view equipment" data-source="banktags" hidden></div>
</td>
"""

    @env.macro
    def setup(tier):
        return f"""
<div>
    <table class="">
        <tbody>
            <tr>
                <td>
                    <table class="equipment equipment-center">
                        <tbody>
                            <tr>
                                <td>
                                    <div class="equipment-div">
                                        { equipment(tier) }
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </td>
                <td>
                    <table class="inventorytable storage-center">
                        <tbody>
                            { inventory(tier) }
                        </tbody>
                    </table>
                </td>
            </tr>
            <tr>
                <td>
                    { spellbook(tier) }
                </td>
                <td>
                    { rune_pouch(tier) }
                </td>
            </tr>
            <tr style="text-align:center">
                { banktags(tier) }
            </tr>
        </tbody>
    </table>
</div>
"""

    @env.macro
    def title(title, image):
        return f"""# <img style="vertical-align:middle" src="{ wiki_url }/images/{ image }.png" width="35"> { title }"""

    @env.macro
    def bank(tier):
        image = 'Mimic' if tier == 'mimic' else f'Clue_scroll_({ tier })'

        return f"""
{ title(f"{ tier.title() } Bank Tags", f"{ image }_detail") }

{ setup(tier) }
"""

    def get_certain_keys(data, keys):
        result = []
        for item in data:
            new_item = {}
            for key in keys:
                if key in item:
                    new_item[key] = item[key]
            if all(key in new_item for key in keys):
                result.append(new_item)
        return result

    def create_filtered_details(tier):
        with open(f'tags/{ tier }/details.json', 'r') as f:
            data = json.load(f)

        path = f"tags/{ tier }/filtered"
        if not os.path.exists(path):
            os.mkdir(path)

        for filter in ["text", "color", "itemIds", "widgetIds"]:
            keys_to_get = ["id", filter]
            result = get_certain_keys(data, keys_to_get)
            f = open(f"tags/{ tier }/filtered/{ filter }.json", "w")
            f.write(json.dumps(result, indent=4))
            f.close()

    @env.macro
    def details(tier):
        create_filtered_details(tier)
        return f"""
{ title(f"{ tier.title() } Clue Details", f"Clue_scroll_({ tier })_detail") }

You may filter the details to import text, color, items, and widgets all together, or each separately via the tabs below

_Copy button is provided on the right_

=== "All"
    ``` json title=""
    --8<-- "tags/{ tier }/details.json"
    ```
=== "Text"
    ``` json title=""
    --8<-- "tags/{ tier }/filtered/text.json"
    ```
=== "Colors"
    ``` json title=""
    --8<-- "tags/{ tier }/filtered/color.json"
    ```
=== "Items"
    ``` json title=""
    --8<-- "tags/{ tier }/filtered/itemIds.json"
    ```
=== "Widgets"
    ``` json title=""
    --8<-- "tags/{ tier }/filtered/widgetIds.json"
    ```
"""
