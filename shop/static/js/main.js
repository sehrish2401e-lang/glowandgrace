// Navbar: scroll par chhota ho
const navbar = document.querySelector('.navbar');
const onScroll = () => navbar.classList.toggle('scrolled', window.scrollY > 40);
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

// Mobile menu
const toggle = document.querySelector('.menu-toggle');
const links = document.querySelector('.nav-links');
if (toggle) toggle.addEventListener('click', () => links.classList.toggle('open'));

// Scroll par cards ek ke baad ek aayen
const items = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
        entries.forEach((e) => {
            if (e.isIntersecting) {
                e.target.classList.add('visible');
                io.unobserve(e.target);
            }
        });
    }, { threshold: 0.12 });
    items.forEach((el) => io.observe(el));
} else {
    items.forEach((el) => el.classList.add('visible'));
}

// Messages 3.5 second baad khud gayab
document.querySelectorAll('.toast').forEach((t) => {
    setTimeout(() => t.classList.add('hide'), 3500);
    setTimeout(() => t.remove(), 4100);
});