import glob
import json
import os
import re
import time
import urllib.parse
import urllib.request

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


def fetch_infobox_item_names():
    """
    Crawls the OSRS Wiki's Bucket API (action=bucket, the infobox_item
    bucket) for item_id -> item_name, paginated 500 rows at a time (~28
    requests for the current catalogue). The query language has no IN/array
    filter to look up just our ~265 known IDs server-side (array literals
    aren't supported by its grammar at all), so a full crawl filtered
    locally is actually fewer total requests than one query per ID would be.

    Unlike the OSRS Wiki's price-mapping API (GE-tradeable items only, ~4,650
    of them), infobox data covers untradeable items too - quest rewards,
    currencies like Coins, cosmetic overrides - which is most of what's left
    unresolved after generate_bank_item_names() checks the price mapping.
    The category exclusions below mirror the ones
    github.com/JZomDev/BankLayoutViewer's own generation script uses to skip
    interface elements, unobtainable/beta/discontinued content, and the like.
    """
    names = {}
    offset = 0
    while True:
        query = (
            "bucket('infobox_item').select('item_id','item_name')"
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
            headers={'User-Agent': 'clue-tags bank-view item name cache (https://github.com/TheLope/clue-tags)'},
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
                names[int(item_ids[0])] = item_name
            except (ValueError, TypeError):
                continue

        if len(rows) < 500:
            break
        offset += 500

    return names


def generate_bank_item_names(ids):
    """
    The bank-view feature (docs/javascripts/bank-view.js) needs item names
    for the ~265 item IDs referenced across all tags/*/bank.txt files. Rather
    than have every visitor's browser fetch wiki data live, resolve just the
    IDs we actually use once here at build time (via fetch_infobox_item_names()
    above) and let the client fetch this small same-origin file.

    Skips re-fetching (and rewriting the file) unless the actual set of item
    IDs has changed since the last time this ran, or the existing data is
    more than NAMES_STALE_AFTER_SECONDS old. The ID-set check handles the
    common case (nothing added to any bank.txt) cheaply; without it, every
    `mkdocs serve` rebuild - including ones triggered by editing unrelated
    markdown - would rewrite item-names.json, and since that file lives
    under docs/, which the dev server watches for live-reload, that would
    itself trigger another rebuild: an infinite reload loop. The staleness
    check on top of that covers the case an already-tracked item gets
    renamed or reclassified upstream without its ID changing - rare, but
    with no expiry it would never get picked up until someone happened to
    touch a bank.txt for an unrelated reason.
    """
    out_path = 'docs/bank/data/item-names.json'
    ids_key = sorted(ids)

    existing = None
    if os.path.exists(out_path):
        try:
            with open(out_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = None

    if existing is not None and existing.get('ids') == ids_key:
        age = time.time() - existing.get('generated_at', 0)
        if age < NAMES_STALE_AFTER_SECONDS:
            return

    try:
        all_names = fetch_infobox_item_names()
        names = {str(i): all_names[i] for i in ids if i in all_names}
    except Exception as e:
        print(f'[bank-view] warning: could not refresh item names ({e})')
        if existing is not None:
            return  # keep the previously generated file rather than clobbering it
        names = {}

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({'ids': ids_key, 'names': names, 'generated_at': time.time()}, f)


def generate_bank_item_icons(ids):
    """
    Self-hosts one small icon per item ID instead of hotlinking
    chisel.weirdgloop.org's sprite server from every visitor's browser -
    same idea as generate_bank_item_names() above, applied to icons too.

    Inspired by github.com/JZomDev/BankLayoutViewer, which does this for its
    *entire* item catalogue (~12,600 items, ~33MB) because it accepts
    arbitrary user-pasted loadouts and can't know ahead of time which items
    it'll need. We don't have that problem - this site only ever needs the
    ~265 IDs actually used across our fixed set of curated tiers - so this
    stays a few dozen KB instead of tens of megabytes.

    Unlike item-names.json, docs/bank/data/icons/ is committed to the repo
    rather than regenerated fresh every build: icons rarely change, and with
    ~265 individual files, re-fetching them all on every CI deploy would be
    a much heavier, more repeated ask of chisel than the single-request name
    lookup. Already-downloaded icons are left in place, so a normal build
    (nothing new added to any bank.txt) hits chisel zero times; only newly
    referenced item IDs get fetched. bank-view.js falls back to the live
    sprite URL client-side if a specific icon is still missing locally, so a
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
        try:
            request = urllib.request.Request(
                f'https://chisel.weirdgloop.org/static/img/osrs-sprite/{item_id}.png',
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                with open(out_path, 'wb') as f:
                    f.write(response.read())
            fetched += 1
        except Exception as e:
            print(f'[bank-view] warning: could not fetch icon for item {item_id} ({e})')
            failed += 1

    if fetched or failed:
        print(f'[bank-view] icons: {fetched} fetched, {skipped} already cached, {failed} failed')


def define_env(env):
    """
    Hook function
    """

    bank_item_ids = collect_bank_item_ids()
    generate_bank_item_names(bank_item_ids)
    generate_bank_item_icons(bank_item_ids)

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
        return f"""
                <a href="{ wiki_url }/w/{ item.replace(' ', '_') }"
                    title="{ item }">
                    <img src="{ wiki_url }/images/{ item.replace(' ', '_') }.png">
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
