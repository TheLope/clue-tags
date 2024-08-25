def define_env(env):
    """
    Hook function
    """

    wiki_url = 'https://oldschool.runescape.wiki'

    @env.macro
    def index_link(tier):
        if tier == 'mimic':
            image = 'Mimic'
        else:
            image = f'Clue_scroll_({ tier })'
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

        if item:
            return f"""
                    <div class="equipment-{ slot } equipment-blank">
                        <div class="equipment-plinkp">
                            { item_render(item) }
                        </div>
                    </div>
                    """
        return f"""
                <div class="equipment-{ slot }">
                    <div class="equipment-plinkp">
                    </div>
                </div>
                """

    @env.macro
    def equipment(tier):
        r = ''

        for slot in ['head','cape','neck','ammo','weapon','torso','legs','shield','gloves','boots','ring']:
            r += equipment_div(env.variables[tier], slot)

        return r

    def inventory_td(d, slot):
        item = d['inventory'][slot]

        if item and '/' in item:
            item, quantity = item.split('/')
            return f"""
                    <td>
                        { item_render(item) }
                        <span class="inv-quantity-text qty-1">{ quantity }
                    </td>
                    """
        elif item:
            return f"""
                    <td>
                        { item_render(item) }
                    </td>
                    """
        return f"""
                <td></td>
                """

    @env.macro
    def inventory(tier):
        r = '<tr>'

        for x in range(28):
            if (x % 4 == 0):
                r += '</tr><tr>'
            r += inventory_td(env.variables[tier], x)

        return r + '</tr>'

    @env.macro
    def spellbook(tier):
        spellbook = env.variables[tier]['spellbook']

        if spellbook == "standard":
            return f"""<img class="icon" src="{ wiki_url }/images/Spellbook.png"/>"""
        elif spellbook == "lunar":
            return f"""<img class="icon" src="{ wiki_url }/images/Lunar_spellbook.png"/>"""
        else:
            return ''

    def rune_pouch_td(d, slot, middle):
        item = d['rune_pouch'][slot]

        if middle:
            return f"""
                    <td class="middle-rune">
                        { item_render(item) }
                    </td>
                    """
        return f"""
                <td>
                    { item_render(item) }
                </td>
                """

    @env.macro
    def rune_pouch(tier):
        d = env.variables[tier]
        if not d['rune_pouch']:
            return ''

        slots = len(d['rune_pouch'])

        if slots == 4:
            divine = True
            r = """
                <table class="runepouchtable divinerunepouch">
                    <tbody>
                        <tr>
                """
        else:
            divine = False
            r = """
                <table class="runepouchtable">
                    <tbody>
                        <tr>
                """

        for x in range(slots):
            if divine and (x == 1 or x == 2):
                r += rune_pouch_td(d, x, True)
            elif not divine and x == 1:
                r += rune_pouch_td(d, x, True)
            else:
                r += rune_pouch_td(d, x, False)

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