// Revela los elementos [data-reveal] la primera vez que entran en pantalla.
const targets = document.querySelectorAll<HTMLElement>('[data-reveal]');
const observer = new IntersectionObserver(
	(entries) => {
		for (const entry of entries) {
			if (!entry.isIntersecting) continue;
			entry.target.classList.add('is-in');
			observer.unobserve(entry.target);
		}
	},
	{ threshold: 0.2, rootMargin: '0px 0px -8% 0px' },
);
targets.forEach((el) => observer.observe(el));
