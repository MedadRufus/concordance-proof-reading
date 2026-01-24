document.addEventListener('DOMContentLoaded', () => {
    const tooltip = document.createElement('div');
    tooltip.className = 'bible-ref-tooltip';
    document.body.appendChild(tooltip);

    const refs = document.querySelectorAll('.bible-ref, .bible-ref-missing');
    refs.forEach(ref => {
        ref.addEventListener('mouseenter', () => {
            const text = ref.getAttribute('data-verse');
            if (!text) return;
            tooltip.textContent = text;
            if (ref.classList.contains('bible-ref-missing')) {
                tooltip.classList.add('missing');
            } else {
                tooltip.classList.remove('missing');
            }
            tooltip.style.display = 'block';
            
            const refRect = ref.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();
            const scrollY = window.scrollY;
            
            let left = refRect.left + (refRect.width / 2) - (tooltipRect.width / 2);
            let top = refRect.top + scrollY - tooltipRect.height - 10;

            if (left < 10) left = 10;
            if (left + tooltipRect.width > window.innerWidth - 10) {
                left = window.innerWidth - tooltipRect.width - 10;
            }
            if (top < scrollY) {
                top = refRect.bottom + scrollY + 10;
            }

            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        });
        ref.addEventListener('mouseleave', () => {
            tooltip.style.display = 'none';
        });
    });
});