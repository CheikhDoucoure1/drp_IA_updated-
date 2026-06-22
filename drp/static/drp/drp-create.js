(function () {
  'use strict';
  var MIN = 3;
  var selected = {};
  var currentDom = null;

  var domSel     = document.getElementById('domaine-select');
  var btnSubmit  = document.getElementById('btn-submit');
  var hiddenWrap = document.getElementById('hidden-fourns');
  var errEl      = document.getElementById('fourns-error');

  if (!domSel || !btnSubmit || !hiddenWrap) return;

  function updateUI() {
    var n = Object.keys(selected).length;
    btnSubmit.disabled = (n < MIN);

    if (currentDom) {
      var wrap = document.getElementById('sel-counter-' + currentDom);
      var txt  = document.getElementById('sel-text-'    + currentDom);
      if (wrap && txt) {
        if (n === 0) {
          wrap.style.background  = '#f0f6ff';
          wrap.style.borderColor = 'rgba(37,99,235,.15)';
          txt.textContent = '0 sélectionné — minimum ' + MIN + ' requis';
        } else if (n < MIN) {
          wrap.style.background  = '#fff7ed';
          wrap.style.borderColor = 'rgba(234,88,12,.3)';
          txt.innerHTML = '<strong>' + n + '</strong> sélectionné(s) — encore ' + (MIN - n) + ' requis';
        } else {
          wrap.style.background  = '#f0fdf4';
          wrap.style.borderColor = 'rgba(22,163,74,.3)';
          txt.innerHTML = '<strong>' + n + '</strong> fournisseur(s) sélectionné(s) ✓';
        }
      }
    }

    hiddenWrap.innerHTML = '';
    Object.keys(selected).forEach(function (pk) {
      var inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = 'fournisseurs';
      inp.value = pk;
      hiddenWrap.appendChild(inp);
    });
  }

  domSel.addEventListener('change', function () {
    var pk = this.value;

    document.querySelectorAll('[id^="dom-section-"]').forEach(function (s) {
      s.style.display = 'none';
    });
    document.querySelectorAll('.drp-f-check').forEach(function (cb) {
      cb.checked = false;
    });
    selected = {};
    currentDom = pk || null;

    if (!pk) { updateUI(); return; }

    var sec = document.getElementById('dom-section-' + pk);
    if (sec) {
      sec.style.display = '';
      var checks = sec.querySelectorAll('.drp-f-check');
      if (checks.length === 3) {
        /* exactement 3 fournisseurs : auto-sélectionner */
        checks.forEach(function (cb) {
          cb.checked = true;
          selected[cb.value] = cb.dataset.nom;
        });
      }
      /* sinon (> 3) : l'utilisateur choisit manuellement */
    }
    updateUI();
  });

  document.addEventListener('change', function (e) {
    if (!e.target.classList.contains('drp-f-check')) return;
    var cb = e.target;
    if (cb.checked) selected[cb.value] = cb.dataset.nom;
    else delete selected[cb.value];
    updateUI();
  });

  btnSubmit.closest('form').addEventListener('submit', function (e) {
    if (Object.keys(selected).length < MIN) {
      e.preventDefault();
      if (errEl) {
        errEl.textContent = 'Sélectionnez au moins ' + MIN + ' fournisseurs (' + Object.keys(selected).length + ' sélectionné(s)).';
        errEl.style.display = '';
      }
      domSel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else if (errEl) {
      errEl.style.display = 'none';
    }
  });
}());
