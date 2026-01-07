document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Konfirmasi Hapus Data
    const deleteButtons = document.querySelectorAll('.btn-delete');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            const confirmDelete = confirm("Apakah Anda yakin ingin menghapus menu Pizza ini? Tindakan ini tidak dapat dibatalkan.");
            if (confirmDelete) {
                window.location.href = this.getAttribute('href');
            }
        });
    });

    // 2. Validasi Form Sederhana
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const hargaInput = form.querySelector('input[name="harga"]');
            if (hargaInput && hargaInput.value < 0) {
                e.preventDefault();
                alert("Harga pizza tidak boleh negatif!");
                hargaInput.focus();
                hargaInput.style.borderColor = "red";
            }
        });
    });

    // 3. Efek Navbar (PERBAIKAN: Selector diganti ke .floating-nav sesuai CSS)
    const navbar = document.querySelector('.floating-nav');
    
    // Pastikan elemen navbar ditemukan sebelum menambah event listener
    if (navbar) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 50) {
                // Saat discroll ke bawah: Background lebih gelap/solid
                navbar.style.background = "rgba(26, 26, 26, 1)"; 
                navbar.style.padding = "10px 30px"; // Sedikit mengecil agar rapi
            } else {
                // Saat di paling atas: Kembali ke semi-transparent
                navbar.style.background = "rgba(26, 26, 26, 0.95)";
                navbar.style.padding = "15px 30px";
            }
        });
    }

});