document.addEventListener('DOMContentLoaded', () => {
    console.log('Script loaded'); // Debug log
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');
    const dropdowns = document.querySelectorAll('.dropdown');

    if (hamburger && navLinks) {
        console.log('Hamburger and navLinks found'); // Debug log
        hamburger.addEventListener('click', () => {
            console.log('Hamburger clicked'); // Debug log
            navLinks.classList.toggle('active');
            document.body.classList.toggle('menu-open');
        });

        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                console.log('Nav link clicked'); // Debug log
                navLinks.classList.remove('active');
                document.body.classList.remove('menu-open');
            });
        });
    } else {
        console.error('Hamburger or navLinks not found'); // Debug error
    }

    dropdowns.forEach(dropdown => {
        const dropbtn = dropdown.querySelector('.dropbtn');
        if (dropbtn) {
            dropbtn.addEventListener('click', () => {
                dropdown.classList.toggle('active');
            });
        }
    });

    const animateSections = document.querySelectorAll(
        '.hero, .about-grid, .categories-section, .order-section, .table-section, .contact-info, .form-section, .section'
    );

    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                entry.target.classList.add(index % 2 === 0 ? 'slide-in-left' : 'slide-in-right');
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    animateSections.forEach(section => {
        observer.observe(section);
    });
});