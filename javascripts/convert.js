var tags = document.getElementById("tags");
var convert = document.getElementById("convert");
var details = document.getElementById("details");
var copy = document.getElementById("copy");

convert.addEventListener('click', () => {
    var lines = tags.value.split("\n");

    var arr = [];
    for (var tag of lines) {
        var split = tag.split(/\s*,\s*/);
        var detail = new Object();
        detail.id = parseInt(split[1]);
        detail.text = split[0];

        if (detail.id != 000000) {
            arr.push(detail);
        }
    }

    var converted = JSON.stringify(arr, null , 4);

    details.style.display = "block";
    details.value = converted;

    var tooltip = document.getElementById("convertTooltip");
    tooltip.innerHTML = "Converted";
})

copy.addEventListener('click', () => {
    var copyText = document.getElementById("details");

    copyText.select();
    copyText.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(copyText.value);

    var tooltip = document.getElementById("copyTooltip");
    tooltip.innerHTML = "Copied";
})
