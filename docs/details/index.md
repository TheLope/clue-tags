{{ title("Clue Details", "Clue_scroll_(Song_of_the_Elves)_detail") }}

All clue tiers **except beginner and master** have unique item IDs for each clue step

This allows us to provide hints on the clue scroll item **without requiring players to open the clue**

## How To

1. Requires the [Clue Details](https://runelite.net/plugin-hub/show/clue-details) RuneLite plugin

2. Import Clue Details
    - Options:
        1. Copy contents of one of the provided clue details lists to your clipboard (see *Tags* below)
        2. If you have tags in the *Custom Item Tags* format, please use the <a href="converter">converter</a>
    - Click the Import button the top of the sidebar panel
        - ![Item Tag Config](images/config.png)
            - **Note**: When exporting, tags will be a single list of all tiers

3. In the plugin configuration, select *Show clue tags*
    - ![Item Tag Config](images/config_show.png)

4. You should now see a tag with the clue description for clues in your inventory
    - ![Item Tag Example](images/example.png)
        - **Note**: The top/bottom text is split based on the first instance of ": " found in the text field.
          - This is configurable via the plugin settings.

## Tags

<div style="width: 100%; padding-bottom:50px;display: flex;flex-direction: row;flex-wrap: wrap;float: left;">
    {{ index_link('easy') }}
    {{ index_link('medium') }}
    {{ index_link('hard') }}
    {{ index_link('elite') }}
</div>