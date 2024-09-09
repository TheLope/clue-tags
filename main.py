import json
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

        for slot in ['head','cape','neck','ammo','weapon','torso','legs','shield','gloves','boots','ring']:
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
        spellbook = env.variables[tier]['spellbook']

        if not spellbook:
            return ''

        return f"""<img class="icon" src="{ wiki_url }/images/{ spellbook.title() }_spellbook.png"/>"""

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
            <table class="runepouchtable {'divinerunepouch' if len(runes) == 4 else ''}">
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
    def setup(tier):
        return f"""
<div class="main-container">
    <div class="left-container">
        <table class="equipment">
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
    </div>
    <div class="left-container">
        <table class="inventorytable">
            <tbody>
                { inventory(tier) }
            </tbody>
        </table>
    </div>
    <div class="right-container">
        <div class="half-container-top">
            { spellbook(tier) }
        </div>
        <div class="half-container-bottom">
            { rune_pouch(tier) }
        </div>
    </div>
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

_Copy button is provided on the right_
``` json title=""
--8<-- "tags/{ tier }/bank.txt"
```
"""

    @env.macro
    def details(tier):
        return f"""
{ title(f"{ tier.title() } Clue Details", f"Clue_scroll_({ tier })_detail") }

_Copy button is provided on the right_
``` json title=""
--8<-- "tags/{ tier }/details.json"
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
