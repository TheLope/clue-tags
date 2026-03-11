/*
mapping file format:
[
	[old_id, new_id],
	[old_id, new_id]
]

if new_id is null, the highlight will be removed.
if old_id is not highlighted, nothing is done

*/

function convertId(widgetId, mappings) {
	for (mapping of mappings) {
		var [oldId, newId] = mapping;
		if (oldId === widgetId.componentId) {
			if (newId) {
				return {
					...widgetId,
					componentId: newId,
				};
			} else {
				return null;
			}
		}
	}
	return widgetId;
}

var convertButton = document.getElementById("convert-widgets");
var copyButton = document.getElementById("copy-onverted");

convertButton.addEventListener('click', () => {
    var tagsBefore = document.getElementById("tags-before");
    var mappingFile = document.getElementById("mapping-file");
    var tagsAfter = document.getElementById("tags-after");

    var tags = JSON.parse(tagsBefore.value);
		var mappings = JSON.parse(mappingFile.value);

    var arr = tags.map(tag => {
			const widgets = tag.widgetIds
				? tag.widgetIds.map(widgetId => convertId(widgetId, mappings)).filter(widgetId => widgetId)
				: null;

			if (!tag.widgetIds && !widgets) {
				return tag;
			}

			return {
				...tag,
				widgetIds: widgets,
			}
    });

    var converted = JSON.stringify(arr);

    tagsAfter.style.display = "block";
    tagsAfter.value = converted;

    var tooltip = document.getElementById("convertTooltip");
    tooltip.innerHTML = "Fixed";
});

copyButton.addEventListener('click', () => {
    var copyText = document.getElementById("tags-after");

    copyText.select();
    copyText.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(copyText.value);

    var tooltip = document.getElementById("copyTooltip");
    tooltip.innerHTML = "Copied";
});
