(function () {
  document.querySelectorAll('.btn-analyser-pdf').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var url = btn.dataset.url;
      var nom = btn.dataset.fournisseur;

      document.getElementById('modalFournisseurNom').textContent = nom;
      document.getElementById('modalSpinner').classList.remove('d-none');
      document.getElementById('modalAnalyseTexte').classList.add('d-none');
      document.getElementById('modalAnalyseTexte').textContent = '';
      document.getElementById('modalAnalyseErreur').classList.add('d-none');

      var modal = new bootstrap.Modal(document.getElementById('modalAnalysePDF'));
      modal.show();

      fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          document.getElementById('modalSpinner').classList.add('d-none');
          var el = document.getElementById('modalAnalyseTexte');
          el.textContent = data.analyse;
          el.classList.remove('d-none');
        })
        .catch(function (err) {
          document.getElementById('modalSpinner').classList.add('d-none');
          var errEl = document.getElementById('modalAnalyseErreur');
          errEl.textContent = 'Une erreur est survenue : ' + err.message;
          errEl.classList.remove('d-none');
        });
    });
  });
})();
