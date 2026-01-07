// main.js - Core functionality
document.addEventListener('DOMContentLoaded', function() {
    
    // Sticky Navbar Logic
    const nav = document.querySelector(".floating-nav");
    
    if (nav) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 50) { 
                // Saat scroll: Hitam solid, nempel atas
                nav.style.background = "rgba(18, 18, 18, 0.95)";
            } else {
                // Saat di atas: Semi transparan
                nav.style.background = "rgba(0, 0, 0, 0.6)";
                nav.style.height = "80px";
                nav.style.padding = "0 50px";
            }
        });
    }

});