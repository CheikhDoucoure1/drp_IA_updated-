(function () {
  function mdToHtml(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  document.querySelectorAll('.btn-analyser-fournisseur').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var url = btn.dataset.url;
      var nom = btn.dataset.fournisseur;

      document.getElementById('modalFournisseurNom').textContent = nom;
      document.getElementById('modalSpinnerFournisseur').classList.remove('d-none');
      document.getElementById('modalAnalyseFournisseurTexte').classList.add('d-none');
      document.getElementById('modalAnalyseFournisseurTexte').innerHTML = '';
      document.getElementById('modalAnalyseFournisseurErreur').classList.add('d-none');

      var modal = new bootstrap.Modal(document.getElementById('modalAnalyseFournisseur'));
      modal.show();

      fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          document.getElementById('modalSpinnerFournisseur').classList.add('d-none');
          var el = document.getElementById('modalAnalyseFournisseurTexte');
          el.innerHTML = mdToHtml(data.analyse);
          el.classList.remove('d-none');
        })
        .catch(function (err) {
          document.getElementById('modalSpinnerFournisseur').classList.add('d-none');
          var errEl = document.getElementById('modalAnalyseFournisseurErreur');
          errEl.textContent = 'Une erreur est survenue : ' + err.message;
          errEl.classList.remove('d-none');
        });
    });
  });
})();
