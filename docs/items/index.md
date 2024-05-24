# Item Tags

All clue tiers **except beginner and master** have unique item IDs for each clue step

This allows us to provide hints on the clue scroll item without requiring players to open the clue

## How To

Requires the [Custom Item Tags](https://runelite.net/plugin-hub/show/custom-items) RuneLite plugin

Paste the contents of the tag files into the *Custom Tags* section of of the plugin configuration

![Item Tag Config](images/config.png)

- Multiple sets of tags can be used at once, simply paste the next set of tags on a new line

You should now see a tag on your current clue

![Item Tag Example](images/example.png)

## Tags

<div style="width: 100%; padding-bottom:50px;display: flex;flex-direction: row;flex-wrap: wrap;float: left;">
    <a href="easy">
        <div style="width: 85px !important; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-bottom:10px">
            <img style="vertical-align:middle" src="../icons/easy.png" width="35">
            <span>Easy</span>
        </div>
    </a>
    <a href="medium">
        <div style="width: 85px !important; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-bottom:10px">
            <img style="vertical-align:middle" src="../icons/medium.png" width="35">
            <span>Medium</span>
        </div>
    </a>
    <a href="hard">
        <div style="width: 85px !important; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-bottom:10px">
            <img style="vertical-align:middle" src="../icons/hard.png" width="35">
            <span>Hard</span>
        </div>
    </a>
    <a href="elite">
        <div style="width: 85px !important; display: flex; flex-direction: column; justify-content: center; align-items: center; padding-bottom:10px">
            <img style="vertical-align:middle" src="../icons/elite.png" width="35">
            <span>Elite</span>
        </div>
    </a>
</div>