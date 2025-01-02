import json
import os
import re


def define_env(env):
    """
    Hook function
    """

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
        <button id="copy" class="equipment">
            <span id="copyTooltip" class="tooltiptext">Copy to clipboard</span>
            Copy Banktag Loadout
        </button>
    </div>
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

        for filter in ["text", "color", "items"]:
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

You may filter the details to import text, color, and items all together, or each separately via the tabs below

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
    --8<-- "tags/{ tier }/filtered/items.json"
    ```
"""

    @env.macro
    def converter():
        return f"""
{ title("Converter", f"Transportation_logo") }

This tool provides a conversion from the old Custom Item Tags format to the new Clue Details format.

<textarea id="tags" class="equipment textarea" placeholder="Paste Custom Item Tags Here">
</textarea>

<div class="tooltip">
    <button id="convert" class="equipment">
        <span id="convertTooltip" class="tooltiptext">Convert Format</span>
        Convert
    </button>
</div>

<textarea id="details" class="equipment textarea" placeholder="Clue Details Output Here">
</textarea>

<div class="tooltip">
    <button id="copy" class="equipment">
        <span id="copyTooltip" class="tooltiptext">Copy to clipboard</span>
        Copy
    </button>
</div>
"""
