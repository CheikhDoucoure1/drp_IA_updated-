(function () {

  function inlineFormat(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code class="ia-code">$1</code>');
  }

  function parseTable(rows) {
    if (rows.length < 1) return '';
    var html = '<div class="table-responsive my-3"><table class="table table-bordered table-sm table-hover ia-table">';
    var headerCells = rows[0];
    html += '<thead><tr>';
    headerCells.forEach(function (cell) {
      html += '<th>' + inlineFormat(cell) + '</th>';
    });
    html += '</tr></thead>';
    var bodyStart = 1;
    if (rows.length > 1 && rows[1].every(function (c) { return /^[-: ]+$/.test(c); })) {
      bodyStart = 2;
    }
    if (bodyStart < rows.length) {
      html += '<tbody>';
      for (var r = bodyStart; r < rows.length; r++) {
        html += '<tr>';
        rows[r].forEach(function (cell) {
          html += '<td>' + inlineFormat(cell) + '</td>';
        });
        html += '</tr>';
      }
      html += '</tbody>';
    }
    html += '</table></div>';
    return html;
  }

  function mdToHtml(text) {
    var html = '';
    var lines = text.split('\n');
    var i = 0;
    var inList = false;
    var tableRows = [];

    function closeList() {
      if (inList) { html += '</ul>'; inList = false; }
    }

    function flushTable() {
      if (tableRows.length > 0) {
        html += parseTable(tableRows);
        tableRows = [];
      }
    }

    while (i < lines.length) {
      var line = lines[i];
      var trimmed = line.trim();

      // Table row
      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        closeList();
        var cells = trimmed.slice(1, -1).split('|').map(function (c) { return c.trim(); });
        tableRows.push(cells);
        i++; continue;
      } else {
        flushTable();
      }

      // Headings
      var hMatch = trimmed.match(/^(#{1,3})\s+(.+)/);
      if (hMatch) {
        closeList();
        html += '<p class="ia-heading">' + inlineFormat(hMatch[2]) + '</p>';
        i++; continue;
      }

      // Horizontal rule
      if (/^[-*_]{3,}$/.test(trimmed)) {
        closeList();
        html += '<hr class="ia-divider">';
        i++; continue;
      }

      // Numbered section with bold title: "1. **Title** : content"
      var secMatch = trimmed.match(/^(\d+)\.\s+\*\*(.+?)\*\*\s*[:\-–]\s*(.*)/);
      if (secMatch) {
        closeList();
        html += '<div class="ia-section">';
        html += '<div class="ia-section-header">';
        html += '<span class="ia-num">' + secMatch[1] + '</span>';
        html += '<span class="ia-section-title">' + inlineFormat(secMatch[2]) + '</span>';
        html += '</div>';
        if (secMatch[3].trim()) {
          html += '<div class="ia-section-body">' + inlineFormat(secMatch[3]) + '</div>';
        }
        // Absorb continuation lines until next section or empty line
        i++;
        while (i < lines.length) {
          var next = lines[i].trim();
          if (next === '' || /^(\d+)\.\s+\*\*/.test(next) || /^(#{1,3})\s/.test(next) || next.startsWith('|')) break;
          if (/^[-*•]\s+/.test(next)) {
            html += '<ul class="ia-list mt-2">';
            while (i < lines.length) {
              var bl = lines[i].trim();
              var bMatch = bl.match(/^[-*•]\s+(.*)/);
              if (!bMatch) break;
              html += '<li>' + inlineFormat(bMatch[1]) + '</li>';
              i++;
            }
            html += '</ul>';
          } else {
            html += '<p class="ia-section-continuation">' + inlineFormat(next) + '</p>';
            i++;
          }
        }
        html += '</div>';
        continue;
      }

      // Simple numbered list without bold title
      var numMatch = trimmed.match(/^(\d+)\.\s+(.+)/);
      if (numMatch) {
        closeList();
        html += '<div class="ia-section ia-section-simple">';
        html += '<span class="ia-num">' + numMatch[1] + '</span>';
        html += '<span class="ia-section-body">' + inlineFormat(numMatch[2]) + '</span>';
        html += '</div>';
        i++; continue;
      }

      // Bullet list
      var bulletMatch = trimmed.match(/^[-*•]\s+(.*)/);
      if (bulletMatch) {
        if (!inList) { html += '<ul class="ia-list">'; inList = true; }
        html += '<li>' + inlineFormat(bulletMatch[1]) + '</li>';
        i++; continue;
      } else {
        closeList();
      }

      // Empty line
      if (trimmed === '') { i++; continue; }

      // Regular paragraph — check if it looks like a recommendation badge
      var recoMatch = trimmed.match(/\*\*(Retenir|À négocier|Ecarter|Écarter|Rejeter)\*\*/i);
      if (recoMatch) {
        var badgeClass = { retenir: 'success', 'à négocier': 'warning', ecarter: 'danger', écarter: 'danger', rejeter: 'danger' }[recoMatch[1].toLowerCase()] || 'secondary';
        var badged = inlineFormat(trimmed).replace(
          new RegExp('<strong>' + recoMatch[1] + '<\/strong>', 'i'),
          '<span class="badge ia-reco-badge bg-' + badgeClass + '">' + recoMatch[1] + '</span>'
        );
        html += '<p class="ia-para">' + badged + '</p>';
        i++; continue;
      }

      html += '<p class="ia-para">' + inlineFormat(trimmed) + '</p>';
      i++;
    }

    closeList();
    flushTable();
    return html;
  }

  document.querySelectorAll('.btn-analyser-fournisseur').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var url = btn.dataset.url;
      var nom = btn.dataset.fournisseur;

      document.getElementById('modalFournisseurNom').textContent = nom;
      document.getElementById('modalSpinnerFournisseur').classList.remove('d-none');
      var texteEl = document.getElementById('modalAnalyseFournisseurTexte');
      texteEl.classList.add('d-none');
      texteEl.innerHTML = '';
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
          texteEl.innerHTML = '<div class="ia-analysis">' + mdToHtml(data.analyse) + '</div>';
          texteEl.classList.remove('d-none');
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
