var copy = document.getElementById("copy");

copy.addEventListener('click', () => {
    var copyText = document.getElementById("banktags");

    copyText.select();
    copyText.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(copyText.value);

    var tooltip = document.getElementById("copyTooltip");
    tooltip.innerHTML = "Copied";
})
