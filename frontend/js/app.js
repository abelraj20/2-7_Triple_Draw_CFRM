// js/app.js

/* game state */
var G = null;
var stats = { hands: 0, wins: 0, pl: 0 };

/* mode and pot options */
function updateModeDependentOptions() {
  var modeEl = document.getElementById('sel-mode');
  var potEl = document.getElementById('sel-pot');
  var potLabelEl = document.getElementById('sel-pot-label');

  if (!modeEl || !potEl || !potLabelEl) return;

  var mode = modeEl.value || '1draw';
  var previous = potEl.value;
  var label = 'Pot:';
  var options = [];

  if (mode === 'cardrem') {
    label = 'No. of cards:';
    options = [0, 1, 2, 3];
  } else if (mode === '1draw') {
    label = 'Pot:';
    options = [3, 5, 7];
  } else if (mode === '2draw') {
    label = 'Pot:';
    options = [7];
  } else {
    label = 'Pot:';
    options = [5];
  }

  potLabelEl.textContent = label;
  potEl.innerHTML = '';

  options.forEach(function(value) {
    var opt = document.createElement('option');
    opt.value = String(value);
    opt.textContent = (mode === 'cardrem') ? String(value) : ('$' + value);
    if (String(value) === previous) opt.selected = true;
    potEl.appendChild(opt);
  });

  var hasSelection = false;
  for (var i = 0; i < potEl.options.length; i++) {
    if (potEl.options[i].selected) {
      hasSelection = true;
      break;
    }
  }

  if (!hasSelection && potEl.options.length > 0) {
    potEl.value = String(options[0]);
  }
}

/* refresh the ui */
function refreshAll() {
  if (!G) {
    setText('pot-amt', '\$0');
    var pc = document.getElementById('player-cards');
    if (pc) pc.innerHTML = '';
    var oc = document.getElementById('opp-cards');
    if (oc) oc.innerHTML = '';
    setText('player-bet', '');
    setText('opp-bet', '');
    hideAllButtons();
    updateStats(stats);
    clearSolverDisplay();
    return;
  }

  var hp = G.humanPos;
  var ap = G.opp(hp);
  var showOpp = false;
  var showOppEl = document.getElementById('chk-show-opp');
  if (showOppEl) showOpp = showOppEl.checked;
  if (G.over) showOpp = true;

  setText('player-name', 'You (' + hp + ')');
  setText('opp-name', 'Opponent (' + ap + ')');
  setDisplay('player-dealer', hp === 'BTN');
  setDisplay('opp-dealer', ap === 'BTN');

  if (G.isNL) {
    setText('player-stack', '$' + (NL_STACK - G.pl[hp].invested));
    setText('opp-stack', '$' + (NL_STACK - G.pl[ap].invested));
  } else {
    setText('player-stack', '');
    setText('opp-stack', '');
  }

  var pb = G.pl[hp].invested;
  var ob = G.pl[ap].invested;
  setText('player-bet', pb > 0 ? 'Invested: $' + pb : '');
  setText('opp-bet', ob > 0 ? 'Invested: $' + ob : '');

  setText('pot-amt', '$' + Math.round(G.pot * 10) / 10);

  renderHand('player-cards', G.pl[hp].hand, true);
  renderHand('opp-cards', G.pl[ap].hand, showOpp);

  setText('draw-info', '');
  setText('deck-info', '');
  setText('disc-info', '');

  updateButtons(G);
  updateSolverDisplay(G);
  updateStats(stats);
}

/* start a new hand */
function startNewHand() {
  var posEl = document.getElementById('sel-pos');
  var modeEl = document.getElementById('sel-mode');
  var potEl = document.getElementById('sel-pot');

  var pos = posEl ? posEl.value : 'BB';
  var mode = modeEl ? modeEl.value : '1draw';
  var selectedValue = potEl ? parseInt(potEl.value, 10) : 5;

  var pot = 5;
  var cardRemovalCount = 0;
  var logDetail = '';

  if (mode === '1draw') {
    pot = selectedValue;
    logDetail = 'Pot $' + pot;
  } else if (mode === 'cardrem') {
    pot = 5;
    cardRemovalCount = selectedValue;
    logDetail = 'No. of cards: ' + cardRemovalCount;
  } else if (mode === '2draw') {
    pot = 7;
    logDetail = 'Pot $' + pot;
  } else {
    pot = 5;
    logDetail = 'Pot $' + pot;
  }

  GAME_MODE = mode;
  GAME_POT = pot;

  G = new GameEngine(pos, mode, pot);
  G.cardRemovalCount = cardRemovalCount;

  stats.hands++;
  clearLog();
  logMsg('Hand #' + stats.hands + ' | ' + mode + ' | ' + logDetail + ' | You are ' + pos, 'system');

  refreshAll();

  if (isOpponentTurn()) {
    setTimeout(opponentTurn, 500);
  }
}

/* turn flow */
function isOpponentTurn() {
  return G && !G.over && G.actor !== G.humanPos;
}

function doAction(action) {
  if (!G || G.over) return;
  if (G.actor !== G.humanPos) return;

  var gameAction = mapSolverToGame(action);
  logAction(G.actor, gameAction);
  G.apply(gameAction);

  checkGameEnd();
  refreshAll();

  if (isOpponentTurn()) {
    setTimeout(opponentTurn, 600);
  }
}

function opponentTurn() {
  if (!G || G.over || !isOpponentTurn()) return;

  var solverAction = getOpponentAction(G);
  var gameAction = mapSolverToGame(solverAction);

  logAction(G.actor, gameAction);
  G.apply(gameAction);

  checkGameEnd();
  refreshAll();

  if (isOpponentTurn()) {
    setTimeout(opponentTurn, 600);
  }
}

/* action mapping */
function mapSolverToGame(solverAct) {
  var map = {
    'k': 'check', 'b': 'bet', 'c': 'call', 'f': 'fold', 'r': 'raise',
    'b40': 'b40', 'b80': 'b80', 'b120': 'b120', 'ba': 'ba',
    'r86': 'r86', 'r111': 'r111', 'ra': 'ra',
    'check': 'check', 'bet': 'bet', 'call': 'call', 'fold': 'fold', 'raise': 'raise'
  };
  return map[solverAct] || solverAct;
}

/* end of hand */
function checkGameEnd() {
  if (!G || !G.over) return;

  var hp = G.humanPos;
  var net = G.payoff(hp);

  if (G.winner && G.phase !== PHASE_SHOWDOWN) {
    logMsg(G.winner + ' wins $' + Math.round(G.pot * 10) / 10 + ' (fold)', G.winner === hp ? 'win' : 'lose');
  } else if (G.phase === PHASE_SHOWDOWN) {
    var btnDesc = G.getHandDescription('BTN');
    var bbDesc = G.getHandDescription('BB');
    logMsg('BTN: ' + btnDesc, 'btn');
    logMsg('BB: ' + bbDesc, 'bb');
    if (G.winner === 'TIE') {
      logMsg('Split pot', 'system');
    } else {
      logMsg(G.winner + ' wins $' + Math.round(G.pot * 10) / 10, G.winner === hp ? 'win' : 'lose');
    }
  }

  logMsg('Your result: ' + (net >= 0 ? '+' : '') + net, net >= 0 ? 'win' : 'lose');

  if (net > 0) stats.wins++;
  stats.pl += net;

  refreshAll();
}

/* page setup */
document.addEventListener('DOMContentLoaded', function() {
  var modeEl = document.getElementById('sel-mode');
  if (modeEl) {
    modeEl.addEventListener('change', updateModeDependentOptions);
  }

  updateModeDependentOptions();
  refreshAll();
});