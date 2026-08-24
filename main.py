"""
mkdocs-macros hook module for this site (see define_env() below), plus the
build-time data pipeline behind two features:
  - bank-view (docs/javascripts/bank-view.js): the visual grid rendering of
    a saved RuneLite bank tag loadout on bank tag pages.
  - the equipment/inventory/rune-pouch/spellbook diagrams also shown on
    those pages, built from docs/bank/data/*.yml via item_render().

Both need to turn OSRS item IDs/names into icons and display names, without
every visitor's browser hitting the OSRS Wiki or chisel.weirdgloop.org
live for it - see fetch_infobox_items()'s docstring for why that matters.
What gets generated, and where:

  docs/bank/data/item-names.json      id -> name, for bank-view. Gitignored;
                                       regenerated when the set of item IDs
                                       referenced across tags/*/bank.txt
                                       changes, or the existing file is more
                                       than NAMES_STALE_AFTER_SECONDS old.

  docs/bank/data/icons/<id>.png       One small icon per bank-view item ID.
                                       Committed to the repo, unlike the
                                       above: re-fetching ~265 individual
                                       files on every build would be a much
                                       heavier ask than the shared name
                                       lookup. Only missing IDs get fetched.

  docs/bank/data/diagram-icons.json   name -> preferred image filename, for
                                       the equipment/inventory/rune-pouch/
                                       spellbook diagrams. Gitignored, same
                                       staleness rule as item-names.json.

All three share a single crawl of the OSRS Wiki's Bucket API
(fetch_infobox_items()) when needs_infobox_crawl() says it's actually
needed, rather than each fetching independently - see that function and
generate_bank_item_names() / generate_bank_item_icons() /
generate_diagram_icon_overrides() for how each uses the shared result.

To force a full refresh locally: delete docs/bank/data/item-names.json,
docs/bank/data/diagram-icons.json, and/or specific files under
docs/bank/data/icons/, then run `mkdocs build` or `mkdocs serve` (needs
network access - the OSRS Wiki, and chisel.weirdgloop.org for any icons
that need it).
"""

import glob
import json
import os
import re
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
    Every unique item name referenced in docs/bank/data/*.yml - the data
    driving item_render() (see below) for the equipment/inventory/rune-pouch
    /spellbook diagrams on bank tag pages. Read directly from the YAML files
    rather than via env.variables, matching collect_bank_item_ids() reading
    tags/*/bank.txt directly rather than through a macro - self-contained,
    not dependent on mkdocs-macros' plugin load order.
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
                    # inventory items may carry a "/quantity" suffix (e.g.
                    # "Aether rune/1025") - strip it, same as inventory_td().
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
    Picks which of a single infobox row's image list to use for `name`.
    Prefers the last entry, but only when every entry matches "<name>
    <number>.png" - a genuine size/pile-tier series - since taking the last
    entry unconditionally picks up unrelated secondary illustrations for
    items whose image list isn't a tier series (see fetch_infobox_items()).
    Falls back to the first entry (infobox convention's primary image) for
    everything else, including the common case of a single-entry list.
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
    Crawls the OSRS Wiki's Bucket API (action=bucket, the infobox_item
    bucket) for item_id -> {name, image}, paginated 500 rows at a time (~28
    requests for the current catalogue). The query language has no IN/array
    filter to look up just our ~265 known IDs server-side (array literals
    aren't supported by its grammar at all), so a full crawl filtered
    locally is actually fewer total requests than one query per ID would be.

    Unlike the OSRS Wiki's price-mapping API (GE-tradeable items only, ~4,650
    of them), infobox data covers untradeable items too - quest rewards,
    currencies like Coins, cosmetic overrides. The category exclusions below
    mirror the ones github.com/JZomDev/BankLayoutViewer's own generation
    script uses to skip interface elements, unobtainable/beta/discontinued
    content, and the like.

    `image` prefers the *last* entry in the infobox's image list, but only
    when the whole list unambiguously looks like a size/pile-tier series -
    every entry named "<item name> <number>.png", e.g. Coins, Revenant
    ether, Numulite ("Coins 1.png" ... "Coins 10000.png"). For most items
    there's only one entry anyway. Some items' image lists mix in an
    unrelated secondary illustration instead (e.g. Blood rune's includes
    "Blood rune (Barbarian Assault).png", a minigame-shop-specific
    reskin) - blindly taking the last entry there would pick that instead
    of the standard icon, so anything that isn't a clean numeric series
    keeps the first entry, which infobox convention treats as the primary
    image. See generate_bank_item_icons() for how this gets used.
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
    Shared staleness check for the small JSON caches below
    (item-names.json, diagram-icons.json): fresh means present, generated
    for exactly this set of keys (item IDs or item names), and not older
    than NAMES_STALE_AFTER_SECONDS.
    """
    if existing is None or existing.get('keys') != keys:
        return False
    age = time.time() - existing.get('generated_at', 0)
    return age < NAMES_STALE_AFTER_SECONDS


def _coverage_regressed(old_count, new_count):
    """
    True if a fresh crawl resolved meaningfully fewer items than the
    existing cache had (more than a 10% drop). A crawl that raises an
    exception is an obvious failure already handled by falling back to the
    existing file; this catches the quieter case where the wiki's Bucket
    schema or category structure shifts under us and the crawl "succeeds"
    but only partially - which would otherwise silently degrade name/icon
    coverage build over build instead of erroring once, loudly.
    """
    return old_count > 0 and new_count < old_count * 0.9


def generate_bank_item_names(ids, infobox_items):
    """
    The bank-view feature (docs/javascripts/bank-view.js) needs item names
    for the ~265 item IDs referenced across all tags/*/bank.txt files. Rather
    than have every visitor's browser fetch wiki data live, resolve just the
    IDs we actually use once here at build time and let the client fetch
    this small same-origin file. `infobox_items` comes from
    fetch_infobox_items() - see needs_infobox_crawl() for when that actually
    runs, since it's shared with generate_bank_item_icons() and
    generate_diagram_icon_overrides() below rather than crawled separately
    by each.

    Skips rewriting the file unless the actual set of item IDs has changed
    since the last time this ran, or the existing data is more than
    NAMES_STALE_AFTER_SECONDS old (see _cache_is_fresh()). The ID-set check
    handles the common case (nothing added to any bank.txt) cheaply; without
    it, every `mkdocs serve` rebuild - including ones triggered by editing
    unrelated markdown - would rewrite item-names.json, and since that file
    lives under docs/, which the dev server watches for live-reload, that
    would itself trigger another rebuild: an infinite reload loop. The
    staleness check on top of that covers the case an already-tracked item
    gets renamed or reclassified upstream without its ID changing - rare,
    but with no expiry it would never get picked up until someone happened
    to touch a bank.txt for an unrelated reason.
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

    if existing is not None and _coverage_regressed(len(existing.get('names', {})), len(names)):
        print(
            f'[bank-view] warning: item name coverage dropped from {len(existing["names"])} '
            f'to {len(names)} resolved - keeping previous item-names.json '
            '(possible wiki API change?)'
        )
        return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({'keys': ids_key, 'names': names, 'generated_at': time.time()}, f)


def generate_bank_item_icons(ids, infobox_items):
    """
    Self-hosts one small icon per item ID instead of hotlinking a live sprite
    server from every visitor's browser - same idea as
    generate_bank_item_names() above, applied to icons too.

    Inspired by github.com/JZomDev/BankLayoutViewer, which does this for its
    *entire* item catalogue (~12,600 items, ~33MB) because it accepts
    arbitrary user-pasted loadouts and can't know ahead of time which items
    it'll need. We don't have that problem - this site only ever needs the
    ~265 IDs actually used across our fixed set of curated tiers - so this
    stays a few dozen KB instead of tens of megabytes.

    Prefers the wiki's own image for each item (infobox_items[id]['image'],
    from fetch_infobox_items() - the biggest pile icon for stackable
    currencies, the single correct icon for everything else) fetched via
    Special:Filepath, which resolves renames/redirects robustly the same
    way github.com/JZomDev/BankLayoutViewer's own downloader uses it. Falls
    back to chisel.weirdgloop.org's sprite server, keyed by ID, when no
    infobox image is available (crawl failed, or this ID isn't in scope for
    that crawl for some reason) - see bank-view.js's docstring for why an
    ID-keyed fallback matters (name-based OSRS Wiki URLs 404 for a
    meaningful slice of real bank items).

    Unlike item-names.json, docs/bank/data/icons/ is committed to the repo
    rather than regenerated fresh every build: icons rarely change, and with
    ~265 individual files, re-fetching them all on every CI deploy would be
    a much heavier, more repeated ask than the shared name/image lookup.
    Already-downloaded icons are left in place, so a normal build (nothing
    new added to any bank.txt) fetches nothing; only newly referenced item
    IDs get fetched. bank-view.js falls back to the live sprite URL
    client-side if a specific icon is still missing locally, so a
    partial/failed fetch here degrades gracefully rather than breaking that
    item's icon.
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


def generate_diagram_icon_overrides(names, infobox_items):
    """
    item_render() (used for the equipment/inventory/rune-pouch/spellbook
    diagrams on bank tag pages, driven by docs/bank/data/*.yml) builds its
    icon URL from the item's *display* name the same naive way bank-view's
    icon logic originally did (oldschool.runescape.wiki/images/<Name>.png) -
    which 404s or shows a misleading icon for the same classes of item
    generate_bank_item_icons() above has to work around: charge-count
    variants, stackable pile icons, renamed items. None of the ~123 names
    currently referenced happen to hit that today, but rather than wait for
    a future addition to silently break, resolve a preferred image filename
    per name here too - from the same infobox crawl shared with
    generate_bank_item_names()/generate_bank_item_icons(), so this adds no
    extra requests when it runs alongside those (see needs_infobox_crawl()).

    A single name can have more than one infobox row behind it: several
    items share a display name with a minigame-specific variant that's a
    genuinely different item ID under the hood (e.g. a plain "Blood rune"
    and a separate "Blood rune" used only in the Barbarian Assault reward
    shop's own UI, each with their own image). Whichever row's image is
    the plain "<name>.png" wins for that name, over any row whose image
    carries an extra qualifier like "(Barbarian Assault)" - picking
    whichever row the crawl happened to reach first would be arbitrary and
    could just as easily grab the minigame-specific one.

    Unlike bank-view's icons, this doesn't self-host the image bytes - the
    equipment/inventory/rune-pouch/spellbook diagrams are a much wider, less
    curated set of pages than the fixed bank-tag tiers, so it stays a live
    oldschool.runescape.wiki hotlink (matching how item_render() already
    worked), just pointed at the *correct* filename instead of a guessed
    one. Names with no infobox match keep the old behavior via item_render()
    falling back to the name itself, so this can only fix icons, never
    break one that already worked.
    """
    out_path = 'docs/bank/data/diagram-icons.json'
    names_key = sorted(names)
    existing = _read_json(out_path)

    if _cache_is_fresh(existing, names_key):
        return

    if infobox_items:
        # Keyed by lowercase name: docs/bank/data/*.yml is hand-typed and
        # doesn't always match the wiki's own capitalization exactly (found
        # "Scythe of vitur" vs. the wiki's "Scythe of Vitur" while building
        # this - a real, pre-existing 404 neither the old naive guess nor a
        # case-sensitive match here would have caught).
        by_name = {}
        for item in infobox_items.values():
            if not item['image']:
                continue
            key = item['name'].lower()
            is_default = item['image'].lower() == f"{item['name']}.png".lower()
            current = by_name.get(key)
            current_is_default = current is not None and current.lower() == f"{item['name']}.png".lower()
            if current is None or (is_default and not current_is_default):
                by_name[key] = item['image']

        # Infobox image references can point at files that don't actually
        # exist - a wiki data-quality issue we hit in practice (an item's
        # infobox row claiming an image that 404s), not something we
        # control. Only names where the resolved image differs from the
        # naive replace(' ', '_') guess item_render() already falls back to
        # are worth a live check: identical ones change nothing either way,
        # and this keeps the check count to a handful rather than all ~123.
        # This comparison is deliberately case-*sensitive* even though the
        # lookup above isn't: wiki URLs are case-sensitive in practice (a
        # capitalization-only difference, like "Scythe of vitur" vs. the
        # wiki's "Scythe of Vitur", is exactly the kind of naive-guess
        # mismatch this whole function exists to catch and fix).
        headers = {'User-Agent': 'clue-tags bank-view item data cache (https://github.com/TheLope/clue-tags)'}
        overrides = {}
        for name in names:
            image = by_name.get(name.lower())
            if not image or image == f'{name}.png':
                continue
            url = f'https://oldschool.runescape.wiki/images/{image.replace(" ", "_")}'
            try:
                request = urllib.request.Request(url, headers=headers, method='HEAD')
                with urllib.request.urlopen(request, timeout=10) as response:
                    if response.status == 200:
                        # item_render() appends its own ".png" (same as it
                        # does for the plain-name fallback), so strip it
                        # here rather than storing it twice.
                        overrides[name] = image[:-4] if image.lower().endswith('.png') else image
            except Exception:
                pass  # leave item_render() to its existing fallback behavior
    elif existing is not None:
        return  # crawl failed or wasn't needed for this reason - keep the previous file
    else:
        overrides = {}

    if existing is not None and _coverage_regressed(len(existing.get('overrides', {})), len(overrides)):
        print(
            f'[bank-view] warning: diagram icon coverage dropped from {len(existing["overrides"])} '
            f'to {len(overrides)} resolved - keeping previous diagram-icons.json '
            '(possible wiki API change?)'
        )
        return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({'keys': names_key, 'overrides': overrides, 'generated_at': time.time()}, f)


def needs_infobox_crawl(bank_ids, diagram_names):
    """
    Whether fetch_infobox_items()'s ~28-request crawl is actually worth
    doing this build: item-names.json or diagram-icons.json is missing or
    stale (see _cache_is_fresh()), or at least one bank-view item is missing
    its local icon. When none of that is true (the common case - nothing
    added to any bank.txt or docs/bank/data/*.yml, nothing stale), this lets
    define_env() skip the crawl entirely rather than paying for it on every
    single build.
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
    generate_bank_item_icons(bank_item_ids, infobox_items)
    generate_diagram_icon_overrides(diagram_item_names, infobox_items)
    diagram_icon_overrides = (_read_json('docs/bank/data/diagram-icons.json') or {}).get('overrides', {})

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
        # Prefer the wiki's own image filename when we have one (see
        # generate_diagram_icon_overrides()) - falls back to the item's own
        # name, matching the site's original behavior, when we don't.
        image = diagram_icon_overrides.get(item, item)

        return f"""
                <a href="{ wiki_url }/w/{ item.replace(' ', '_') }"
                    title="{ item }">
                    <img src="{ wiki_url }/images/{ image.replace(' ', '_') }.png">
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
