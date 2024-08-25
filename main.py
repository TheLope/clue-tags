def define_env(env):
    """
    Hook function
    """

    wiki_url = 'https://oldschool.runescape.wiki'

    @env.macro
    def index_link(tier):
        image = f'Clue_scroll_({ tier })'
        if tier == 'mimic':
            image = 'Mimic'

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

    def inventory_td(d, index):
        item = d['inventory'][index]

        if item and '/' in item:
            item, quantity = item.split('/')
            return f"""
                    <td>
                        { item_render(item) }
                        <span class="inv-quantity-text qty-1">{ quantity }
                    </td>
                    """
        return f"""
                <td>
                    { item_render(item) if item else ''}
                </td>
                """

    @env.macro
    def inventory(tier):
        r = '<tr>'

        for index in range(28):
            if (index % 4 == 0):
                r += '</tr><tr>'
            r += inventory_td(env.variables[tier], index)

        return r + '</tr>'

    @env.macro
    def spellbook(tier):
        spellbook = env.variables[tier]['spellbook']

        if spellbook == "standard":
            return f"""<img class="icon" src="{ wiki_url }/images/Spellbook.png"/>"""
        elif spellbook == "lunar":
            return f"""<img class="icon" src="{ wiki_url }/images/Lunar_spellbook.png"/>"""
        return ''

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

        divine = False
        if len(runes) == 4:
            divine = True

        r = f"""
            <table class="runepouchtable {'divinerunepouch' if divine else ''}">
                <tbody>
                    <tr>
            """

        for index in range(len(runes)):
            if index == 1 or (divine and index == 2):
                r += rune_pouch_td(runes, index, True)
            else:
                r += rune_pouch_td(runes, index, False)

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
    def bank(tier):
        if tier == 'mimic':
            image = 'Mimic'
        else:
            image = f'Clue_scroll_({ tier })'
        return f"""
# <img style="vertical-align:middle" src="{ wiki_url }/images/{ image }_detail.png" width="35"> { tier.title() } Bank Tags

{ setup(tier) }

_Copy button is provided on the right_
``` json title=""
--8<-- "tags/{ tier }/bank.txt"
```
"""

    @env.macro
    def items(tier):
        return f"""
# <img style="vertical-align:middle" src="{ wiki_url }/images/Clue_scroll_({ tier })_detail.png" width="35"> { tier.title() } Item Tags

_Copy button is provided on the right_
``` yaml title=""
--8<-- "tags/{ tier }/item.yml"
```
"""