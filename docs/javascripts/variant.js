function updateVariantToggle() {
    const toggle = document.querySelector('.variant')

    if (!toggle) return

    const root = new URL(toggle.dataset.variantBase.replace(/\/?$/, '/'), location.href)
    const unmaxed = root.pathname.endsWith('/unmaxed/')
    const roots = {
        maxed: unmaxed ? new URL('../', root) : root,
        unmaxed: unmaxed ? root : new URL('unmaxed/', root)
    }
    const page = location.pathname.slice(root.pathname.length) + location.hash

    for (const option of toggle.querySelectorAll('.variant__option')) {
        const variant = option.dataset.variant
        const active = variant === (unmaxed ? 'unmaxed' : 'maxed')

        option.href = new URL(page, roots[variant]).href
        option.classList.toggle('variant__option--active', active)

        if (active) {
            option.setAttribute('aria-current', 'page')
        } else {
            option.removeAttribute('aria-current')
        }
    }
}

if (typeof document$ !== 'undefined') {
    document$.subscribe(updateVariantToggle)
} else {
    document.addEventListener('DOMContentLoaded', updateVariantToggle)
}
