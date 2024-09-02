# Clue Details

All clue tiers **except beginner and master** have unique item IDs for each clue step

This allows us to provide hints **without requiring players to open the clue**

## How To

Requires the [Clue Details](https://runelite.net/plugin-hub/show/clue-details) RuneLite plugin

To import:

- Copy contents of one of the provided clue descriptions lists to your clipboard
- Import via right-clicking the *Clue Details* text at the top of the sidebar configuration

![Item Tag Config](images/config.png)

You should now see a new infobox with the clue description for clues in your inventory

![Item Tag Example](images/example.png)

- Use alt to move the text to your desired location

## Tags

<div style="width: 100%; padding-bottom:50px;display: flex;flex-direction: row;flex-wrap: wrap;float: left;">
    {{ index_link('easy') }}
    {{ index_link('medium') }}
    {{ index_link('hard') }}
    {{ index_link('elite') }}
</div>