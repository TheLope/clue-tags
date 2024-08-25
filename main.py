def define_env(env):
    """
    Hook function
    """

    @env.macro
    def index_link(tier):
        if tier == 'mimic':
            image = 'Mimic'
        else:
            image = f'Clue_scroll_({ tier })'
        return f"""
                <a href="{ tier }">
                    <div style="width: 85px !important; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-bottom:10px">
                        <img style="vertical-align:middle" src="{ env.variables.wiki_url }/images/{ image }_detail.png" width="35">
                        <span>{ tier.title() }</span>
                    </div>
                </a>
                """

    def equipment_div(d, slot):
        if d['equipment'][slot]:
            return f"""
                    <div class="equipment-{ slot } equipment-blank">
                        <div class="equipment-plinkp">
                            <a href="{ env.variables.wiki_url }/w/{ d['equipment'][slot] }"
                               title="{ d['equipment'][slot].replace('_', ' ') }">
                                <img src="{ env.variables.wiki_url }/images/{ d['equipment'][slot] }.png">
                            </a>
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
        if d['inventory'][slot] and '/' in d['inventory'][slot]:
            item, quantity = d['inventory'][slot].split('/')
            return f"""
                    <td>
                        <a href="{ env.variables.wiki_url }/w/{ item }"
                           title="{ item.replace('_', ' ') }">
                            <img src="{ env.variables.wiki_url }/images/{ item }.png">
                        </a>
                        <span class="inv-quantity-text qty-1">{ quantity }
                    </td>
                    """
        elif d['inventory'][slot]:
            return f"""
                    <td>
                        <a href="{ env.variables.wiki_url }/w/{ d['inventory'][slot] }"
                           title="{ d['inventory'][slot].replace('_', '' '') }">
                            <img src="{ env.variables.wiki_url }/images/{ d['inventory'][slot] }.png">
                        </a>
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
            return f"""<img class="icon" src="{ env.variables.wiki_url }/images/Spellbook.png"/>"""
        elif spellbook == "lunar":
            return f"""<img class="icon" src="{ env.variables.wiki_url }/images/Lunar_spellbook.png"/>"""
        else:
            return ''

    def rune_pouch_td(d, slot, middle):
        if middle:
            return f"""
                    <td class="middle-rune">
                        <a href="{ env.variables.wiki_url }/w/{ d['rune_pouch'][slot] }"
                            title="{ d['rune_pouch'][slot].replace('_', ' ') }">
                            <img src="{ env.variables.wiki_url }/images/{ d['rune_pouch'][slot] }.png">
                        </a>
                    </td>
                    """
        return f"""
                <td>
                    <a href="{ env.variables.wiki_url }/w/{ d['rune_pouch'][slot] }"
                        title="{ d['rune_pouch'][slot].replace('_', ' ') }">
                        <img src="{ env.variables.wiki_url }/images/{ d['rune_pouch'][slot] }.png">
                    </a>
                </td>
                """

    @env.macro
    def rune_pouch(tier):
        if not env.variables[tier]['rune_pouch']:
            return ''

        slots = len(env.variables[tier]['rune_pouch'])

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
                r += rune_pouch_td(env.variables[tier], x, True)
            elif not divine and x == 1:
                r += rune_pouch_td(env.variables[tier], x, True)
            else:
                r += rune_pouch_td(env.variables[tier], x, False)

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
# <img style="vertical-align:middle" src="{ env.variables.wiki_url }/images/{ image }_detail.png" width="35"> { tier.title() } Bank Tags

{ setup(tier) }

_Copy button is provided on the right_
``` json title=""
--8<-- "tags/{ tier }/bank.txt"
```
"""

    @env.macro
    def items(tier):
        return f"""
# <img style="vertical-align:middle" src="{ env.variables.wiki_url }/images/Clue_scroll_({ tier })_detail.png" width="35"> { tier.title() } Item Tags

_Copy button is provided on the right_
``` yaml title=""
--8<-- "tags/{ tier }/item.yml"
```
"""