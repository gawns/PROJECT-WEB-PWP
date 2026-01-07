// admin.js - Admin specific functionality
document.addEventListener('DOMContentLoaded', function() {
    
    // Konfirmasi Hapus Data
    const deleteButtons = document.querySelectorAll('.btn-delete');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            const confirmDelete = confirm("Apakah Anda yakin ingin menghapus data ini? Tindakan ini tidak dapat dibatalkan.");
            if (confirmDelete) {
                window.location.href = this.getAttribute('href');
            }
        });
    });
    
    // Form Validation
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const hargaInput = form.querySelector('input[name="harga"]');
            if (hargaInput && hargaInput.value < 0) {
                e.preventDefault();
                alert("Harga tidak boleh negatif!");
                hargaInput.focus();
                hargaInput.style.borderColor = "red";
            }
        });
    });
    
    // Status Change Animation
    const statusSelects = document.querySelectorAll('.status-select');
    
    statusSelects.forEach(select => {
        select.addEventListener('change', function() {
            this.parentElement.classList.add('status-updated');
            setTimeout(() => {
                this.parentElement.classList.remove('status-updated');
            }, 500);
        });
    });

});