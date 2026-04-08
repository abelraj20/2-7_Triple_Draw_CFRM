// js/ui.js

/* action colours and labels */
var colors = {
  'k': 'color-check', 'c': 'color-call', 'f': 'color-fold',
  'b': 'color-bet', 'r': 'color-raise',

  'b40': 'color-b40', 'b80': 'color-b80', 'b120': 'color-b120', 'ba': 'color-ba',
  'r86': 'color-r86', 'r111': 'color-r111', 'ra': 'color-ra'
};

var labels = {
  'k': 'Check', 'c': 'Call', 'f': 'Fold', 'b': 'Bet', 'r': 'Raise',

  'b40': 'Bet 40%', 'b80': 'Bet 80%', 'b120': 'Bet 120%', 'ba': 'All-in',
  'r86': 'Raise 86%', 'r111': 'Raise 111%', 'ra': 'All-in'
};

/* buckets hidden from the frontend */
var HIDDEN_BUCKETS = {
  '2-Pair': true,
  'Trips': true,
  'Extra': true
};

function isHiddenBucket(bucket) {
  return !!HIDDEN_BUCKETS[bucket];
}

function getActionColorClass(act) {
  if (colors[act]) return colors[act];

  if (typeof act === 'string') {
    if (act === 'check' || act === 'k') return 'color-check';
    if (act === 'call'  || act === 'c') return 'color-call';
    if (act === 'fold'  || act === 'f') return 'color-fold';

    if (act[0] === 'b') return 'color-bet';
    if (act[0] === 'r') return 'color-raise';
  }
  return 'color-call';
}

function getActionLabel(act) {
  if (labels[act]) return labels[act];

  if (typeof act === 'string') {
    if (act === 'check') return 'Check';
    if (act === 'call')  return 'Call';
    if (act === 'fold')  return 'Fold';
    if (act === 'bet')   return 'Bet';
    if (act === 'raise') return 'Raise';
    if (act === 'ba' || act === 'ra') return 'All-in';

    if (act[0] === 'b') return 'Bet ' + act.slice(1) + '%';
    if (act[0] === 'r') return 'Raise ' + act.slice(1) + '%';
  }
  return String(act);
}

function getActionSortKey(act) {
  if (typeof act !== 'string') return 9999;

  if (act === 'check' || act === 'k') return 10;
  if (act === 'bet'   || act === 'b') return 20;
  if (act === 'b40') return 21;
  if (act === 'b80') return 22;
  if (act === 'b120') return 23;
  if (act === 'ba') return 24;
  if (act === 'call'  || act === 'c') return 30;
  if (act === 'fold'  || act === 'f') return 40;
  if (act === 'raise' || act === 'r') return 50;
  if (act === 'r86') return 51;
  if (act === 'r111') return 52;
  if (act === 'ra') return 53;

  if (/^b\d+$/.test(act)) return 25;
  if (/^r\d+$/.test(act)) return 54;

  return 9999;
}

function getDisplayActions(actions) {
  if (!actions || !actions.length) return [];

  return actions.slice().sort(function (a, b) {
    var ka = getActionSortKey(a);
    var kb = getActionSortKey(b);
    if (ka !== kb) return ka - kb;
    return String(a).localeCompare(String(b));
  });
}

/* card rendering */
function renderCard(card, faceUp) {
  var div = document.createElement('div');
  if (faceUp) {
    div.className = 'card card-face black';
    div.innerHTML =
      '<span class="card-rank">' + card[0] + '</span>';
  } else {
    div.className = 'card card-back';
  }
  return div;
}

function renderHand(containerId, hand, faceUp) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  if (!hand) return;

  hand.forEach(function (c) {
    el.appendChild(renderCard(c, faceUp));
  });
}

/* action buttons */
var ALL_BTN_IDS = [
  'btn-fold', 'btn-check', 'btn-call', 'btn-bet', 'btn-raise',
  'btn-b40', 'btn-b80', 'btn-b120', 'btn-ba',
  'btn-r86', 'btn-r111', 'btn-ra'
];

function hideAllButtons() {
  ALL_BTN_IDS.forEach(function (id) {
    var el = document.getElementById(id);
    if (el) {
      el.disabled = true;
      el.style.display = 'none';
    }
  });
}

function updateButtons(game) {
  hideAllButtons();
  if (!game || game.over || game.actor !== game.humanPos) return;

  var actions = game.legalActions();
  var info = game.getBetInfo();

  actions.forEach(function (a) {
    var btnId = null;

    switch (a) {
      case 'fold':
        btnId = 'btn-fold';
        break;

      case 'check':
        btnId = 'btn-check';
        break;

      case 'call':
        btnId = 'btn-call';
        var callEl = document.getElementById('call-amt');
        if (callEl) callEl.textContent = '$' + info.toCall;
        break;

      case 'bet':
        btnId = 'btn-bet';
        var betEl = document.getElementById('bet-amt');
        if (betEl) betEl.textContent = '$' + info.betSize;
        break;

      case 'raise':
        btnId = 'btn-raise';
        var raiseEl = document.getElementById('raise-amt');
        if (raiseEl) raiseEl.textContent = '$' + info.raiseSize;
        break;

      case 'b40':
        btnId = 'btn-b40';
        var el40 = document.getElementById('b40-amt');
        if (el40) el40.textContent = '$' + info.b40;
        break;

      case 'b80':
        btnId = 'btn-b80';
        var el80 = document.getElementById('b80-amt');
        if (el80) el80.textContent = '$' + info.b80;
        break;

      case 'b120':
        btnId = 'btn-b120';
        var el120 = document.getElementById('b120-amt');
        if (el120) el120.textContent = '$' + info.b120;
        break;

      case 'ba':
        btnId = 'btn-ba';
        var elba = document.getElementById('ba-amt');
        if (elba) elba.textContent = '$' + info.ba;
        break;

      case 'r86':
        btnId = 'btn-r86';
        var elr86 = document.getElementById('r86-amt');
        if (elr86) elr86.textContent = '$' + info.r86;
        break;

      case 'r111':
        btnId = 'btn-r111';
        var elr111 = document.getElementById('r111-amt');
        if (elr111) elr111.textContent = '$' + info.r111;
        break;

      case 'ra':
        btnId = 'btn-ra';
        var elra = document.getElementById('ra-amt');
        if (elra) elra.textContent = '$' + info.ra;
        break;
    }

    if (btnId) {
      var btn = document.getElementById(btnId);
      if (btn) {
        btn.style.display = 'flex';
        btn.disabled = false;
      }
    }
  });
}

/* solver data lookup */
function _getSolverVariantKeyForGame(game) {
  if (!game) return null;

  if (game.mode === 'cardrem') {
    var n = Number(game.cardRemovalCount);
    if (!Number.isFinite(n) || n < 0 || n > 3) n = 0;
    return 'cfr_rem_' + n;
  }

  return game.mode;
}

function _getSolverPotKeyForGame(game) {
  if (!game) return null;

  if (game.mode === 'cardrem') return '5';
  return String(game.startPot);
}

function _getPotDataForGame(game) {
  if (!game || typeof SOLVER_DATA === 'undefined' || !SOLVER_DATA) return null;

  var variantKey = _getSolverVariantKeyForGame(game);
  var modeData = SOLVER_DATA[variantKey];
  if (!modeData || !modeData.pots) return null;

  var potKey = _getSolverPotKeyForGame(game);
  var potData = modeData.pots[potKey];

  if (!potData) {
    var potKeys = Object.keys(modeData.pots);
    if (potKeys.length > 0) potData = modeData.pots[potKeys[0]];
  }

  return potData || null;
}

function getSolverSequence(game) {
  var potData = _getPotDataForGame(game);
  if (!potData || !potData.strategies || !potData.strategies.sequences) return null;

  var solverKey = game.getSolverKey();
  return potData.strategies.sequences[solverKey] || null;
}

function getSolverEVSequence(game) {
  var potData = _getPotDataForGame(game);
  if (!potData || !potData.ev || !potData.ev.sequences) return null;

  var solverKey = game.getSolverKey();
  return potData.ev.sequences[solverKey] || null;
}

/* reach adjusted bucket frequencies */
function getSolverBucketFreqSequence(game) {
  var potData = _getPotDataForGame(game);
  if (!potData || !potData.bucket_freq_by_sequence || !potData.bucket_freq_by_sequence.sequences) return null;
  var solverKey = game.getSolverKey();
  return potData.bucket_freq_by_sequence.sequences[solverKey] || null;
}

function applyFreqSeqToSeqData(seqData, freqSeq) {
  if (!seqData || !seqData.rows || !freqSeq || !freqSeq.bucket_freq) return seqData;
  var tf = Number(freqSeq.total_freq || 0);
  var out = Object.assign({}, seqData);
  out.rows = seqData.rows.map(function (r) {
    var rr = Object.assign({}, r);
    if (rr && rr.bucket && freqSeq.bucket_freq[rr.bucket] !== undefined) {
      var mass = Number(freqSeq.bucket_freq[rr.bucket]);
      rr.rate = (tf > 0) ? (mass / tf) * 100.0 : 0.0;
    }
    return rr;
  });
  return out;
}

function buildBucketMap(seqData) {
  if (!seqData || !seqData.rows) return {};

  var actions = getDisplayActions(seqData.actions || []);
  var map = {};

  for (var i = 0; i < seqData.rows.length; i++) {
    var row = seqData.rows[i];
    var strat = {};

    for (var j = 0; j < actions.length; j++) {
      var a = actions[j];
      strat[a] = (row[a] !== undefined) ? row[a] : 0;
    }

    map[row.bucket] = { rate: row.rate || 0, strategy: strat };
  }
  return map;
}

function buildEvMap(evSeq) {
  if (!evSeq || !evSeq.rows) return {};
  var map = {};
  for (var i = 0; i < evSeq.rows.length; i++) {
    var r = evSeq.rows[i];
    map[r.bucket] = r;
  }
  return map;
}

function applyEvClass(td, v) {
  td.classList.remove('ev-positive', 'ev-negative', 'ev-zero');
  if (v > 0) td.classList.add('ev-positive');
  else if (v < 0) td.classList.add('ev-negative');
  else td.classList.add('ev-zero');
}

function computeOverallFromRows(seqData) {
  if (!seqData || !seqData.rows) return {};

  var actions = getDisplayActions(seqData.actions || []);
  var sumRate = 0;
  var totals = {};

  for (var i = 0; i < seqData.rows.length; i++) {
    var row = seqData.rows[i];
    var w = Number(row.rate) || 0;
    sumRate += w;

    for (var j = 0; j < actions.length; j++) {
      var a = actions[j];
      var p = Number(row[a]) || 0;
      totals[a] = (totals[a] || 0) + (w * p / 100.0);
    }
  }

  var out = {};
  if (sumRate <= 0) {
    for (var k = 0; k < actions.length; k++) out[actions[k]] = 0;
    return out;
  }

  for (var k2 = 0; k2 < actions.length; k2++) {
    var a2 = actions[k2];
    out[a2] = (totals[a2] / sumRate) * 100.0;
  }
  return out;
}

/* bucket order */
var DEFAULT_BUCKET_ORDER = [
  "75","76","85","86","87","95","96","97","98",
  "T5","T6","T7","T8","T9",
  "J8","J9","Q","K","A",
  "22","33","44","55","66","77","88","99",
  "TT","JJ","QQ","KK","AA",
  "Str.",
  "Straight"
];

function getBucketOrderForGame(game, seqData) {
  var buckets = [];

  if (seqData && seqData.rows && seqData.rows.length) {
    seqData.rows.forEach(function (r) {
      if (r && r.bucket && !isHiddenBucket(r.bucket)) buckets.push(r.bucket);
    });
  }
  if (!buckets.length) return DEFAULT_BUCKET_ORDER.filter(function (b) { return !isHiddenBucket(b); });

  var seen = {};
  var uniq = [];
  buckets.forEach(function (b) {
    if (!seen[b]) {
      seen[b] = true;
      uniq.push(b);
    }
  });

  var canon = {};
  DEFAULT_BUCKET_ORDER.forEach(function (b, i) { canon[b] = i; });

  uniq.sort(function (a, b) {
    var ia = (canon[a] !== undefined) ? canon[a] : 100000;
    var ib = (canon[b] !== undefined) ? canon[b] : 100000;
    if (ia !== ib) return ia - ib;
    return String(a).localeCompare(String(b));
  });

  return uniq;
}

/* solver display */
function updateSolverDisplay(game) {
  var rawSeqData = getSolverSequence(game);
  if (!rawSeqData) {
    clearSolverDisplay();
    return;
  }

  var freqSeq = getSolverBucketFreqSequence(game);
  var seqData = applyFreqSeqToSeqData(rawSeqData, freqSeq);
  var actions = getDisplayActions(seqData.actions || []);
  var buckets = buildBucketMap(seqData);
  var bucketOrder = getBucketOrderForGame(game, seqData);

  var overall = seqData.overall;
  var hasOverall = false;

  if (overall) {
    var s = 0;
    for (var i = 0; i < actions.length; i++) s += (Number(overall[actions[i]]) || 0);
    hasOverall = (s > 0.0001);
  }
  if (!hasOverall || freqSeq) overall = computeOverallFromRows(seqData);

  var overallBar = document.getElementById('overall-freq-bar');
  if (overallBar) {
    overallBar.innerHTML = '';
    var count = actions.length;

    if (count === 0) {
      overallBar.innerHTML =
        '<div class="freq-bar-segment color-check" style="width:100%">' +
        '<span class="freq-label">No data</span><span class="freq-pct">-</span></div>';
    } else {
      var equalWidth = 100 / count;
      actions.forEach(function (act) {
        var pct = Number(overall[act] || 0);
        var div = document.createElement('div');
        div.className = 'freq-bar-segment ' + getActionColorClass(act);
        div.style.width = equalWidth + '%';
        div.innerHTML =
          '<span class="freq-label">' + getActionLabel(act) + '</span>' +
          '<span class="freq-pct">' + pct.toFixed(1) + '%</span>';
        overallBar.appendChild(div);
      });
    }
  }

  var evSeq = getSolverEVSequence(game);
  var evMap = buildEvMap(evSeq);

  var tbody = document.getElementById('bucket-col-1');
  if (!tbody) return;
  tbody.innerHTML = '';

  bucketOrder.forEach(function (bName) {
    if (isHiddenBucket(bName)) return;

    var bd = buckets[bName];
    var er = evMap[bName];

    if (!bd || Number(bd.rate || 0) < 0.0001) return;

    var tr = document.createElement('tr');
    tr.dataset.bucket = bName;

    var tdStrat = document.createElement('td');
    tdStrat.className = 'col-strategy';

    var wrap = document.createElement('div');
    wrap.className = 'bucket-strategy-cell';

    var tag = document.createElement('span');
    tag.className = 'bucket-tag';
    tag.textContent = bName;

    var barDiv = document.createElement('div');
    barDiv.className = 'strategy-bar';

    if (bd && bd.strategy) {
      actions.forEach(function (act) {
        var pct = bd.strategy[act] || 0;
        if (pct > 0) {
          var seg = document.createElement('div');
          seg.className = 'bar-segment ' + getActionColorClass(act);
          seg.style.width = pct + '%';
          seg.title = getActionLabel(act) + ': ' + pct + '%';
          barDiv.appendChild(seg);
        }
      });
    }

    wrap.appendChild(tag);
    wrap.appendChild(barDiv);
    tdStrat.appendChild(wrap);
    tr.appendChild(tdStrat);

    var tdRate = document.createElement('td');
    tdRate.className = 'col-rate';
    tdRate.textContent = bd ? (Number(bd.rate).toFixed(2) + '%') : '0.00%';
    tr.appendChild(tdRate);

    var tdBtn = document.createElement('td');
    tdBtn.className = 'col-ev-btn';
    if (er && er.btn_ev !== undefined && er.btn_ev !== null) {
      var vBtn = Number(er.btn_ev);
      tdBtn.textContent = vBtn.toFixed(3);
      applyEvClass(tdBtn, vBtn);
    } else {
      tdBtn.textContent = '-';
      tdBtn.classList.add('ev-zero');
    }
    tr.appendChild(tdBtn);

    var tdBb = document.createElement('td');
    tdBb.className = 'col-ev-bb';
    if (er && er.bb_ev !== undefined && er.bb_ev !== null) {
      var vBb = Number(er.bb_ev);
      tdBb.textContent = vBb.toFixed(3);
      applyEvClass(tdBb, vBb);
    } else {
      tdBb.textContent = '-';
      tdBb.classList.add('ev-zero');
    }
    tr.appendChild(tdBb);

    tbody.appendChild(tr);
  });

  highlightPlayerBucket(game);
}

function highlightPlayerBucket(game) {
  if (!game) return;
  var bucket = game.getBucket(game.humanPos);
  if (isHiddenBucket(bucket)) bucket = null;

  document.querySelectorAll('#bucket-col-1 tr').forEach(function (row) {
    row.classList.remove('active-bucket');
    if (row.dataset && row.dataset.bucket === bucket) row.classList.add('active-bucket');
  });
}

function clearSolverDisplay() {
  var bar = document.getElementById('overall-freq-bar');
  if (bar) {
    bar.innerHTML =
      '<div class="freq-bar-segment color-check" style="width:100%">' +
      '<span class="freq-label">No data</span><span class="freq-pct">-</span></div>';
  }

  var tb = document.getElementById('bucket-col-1');
  if (tb) tb.innerHTML = '';
}

/* opponent action */
function getOpponentAction(game) {
  var seqData = getSolverSequence(game);
  if (!seqData) return randomFallback(game);

  var actions = seqData.actions || [];
  var buckets = buildBucketMap(seqData);

  var oppPos = game.actor;
  var bucket = game.getBucket(oppPos);
  var bd = buckets[bucket];

  if ((!bd || !bd.strategy) && isHiddenBucket(bucket) && buckets['Extra']) {
    bd = buckets['Extra'];
  }

  if (!bd || !bd.strategy) return randomFallback(game);

  var r = Math.random() * 100;
  var cum = 0;
  for (var i = 0; i < actions.length; i++) {
    cum += (bd.strategy[actions[i]] || 0);
    if (r <= cum) return actions[i];
  }
  return actions[actions.length - 1] || randomFallback(game);
}

function randomFallback(game) {
  var actions = game.legalActions();
  if (actions.indexOf('check') >= 0) return 'check';
  if (actions.indexOf('call') >= 0) return 'call';
  return actions[0] || 'fold';
}

/* session stats */
function updateStats(stats) {
  var handsEl = document.getElementById('stat-hands');
  if (handsEl) handsEl.textContent = stats.hands;

  var plEl = document.getElementById('stat-pl');
  if (plEl) {
    plEl.textContent = (stats.pl >= 0 ? '+' : '') + stats.pl;
    plEl.style.color = stats.pl >= 0 ? '#4fc3f7' : '#e94560';
  }
}

/* action log */
function logMsg(msg, type) {
  var el = document.getElementById('action-log');
  if (!el) return;

  var div = document.createElement('div');
  div.className = 'log-entry log-' + (type || 'system');
  div.textContent = msg;

  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

function clearLog() {
  var el = document.getElementById('action-log');
  if (el) el.innerHTML = '';
}

function logAction(pos, action) {
  logMsg(pos + ': ' + getActionLabel(action), pos === 'BTN' ? 'btn' : 'bb');
}

/* small helpers */
function setText(id, text) {
  var el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setDisplay(id, show) {
  var el = document.getElementById(id);
  if (el) el.style.display = show ? 'flex' : 'none';
}