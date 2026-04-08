// js/game.js

/* main game settings */
var GAME_MODE = '1draw';
var GAME_POT = 5;

var LIMIT_RAISE_SCHEDULE = [1, 2, 3, 4];
var LIMIT_MAX_RAISES = 3;

var NL_STACK = 25;
var NL_BET_FRACS = { b40: 0.40, b80: 0.80, b120: 1.20, ba: 'allin' };
var NL_RAISE_OPTIONS = {
  b40:  { r86: 0.86, ra: 'allin' },
  b80:  { r111: 1.11, ra: 'allin' },
  b120: { ra: 'allin' },
  r86:  { ra: 'allin' },
  r111: { ra: 'allin' },
  ba:   {},
  ra:   {}
};

var PHASE_BET = 'BET';
var PHASE_SHOWDOWN = 'SHOWDOWN';

var PHASE_LABEL_MAP = {
  BET: 'Final Round Betting',
  SHOWDOWN: 'Showdown'
};

/* rank-only seed helpers */
function buildRankOnlyDeckCounts() {
  var counts = {};
  for (var r = 2; r <= 14; r++) counts[r] = 4;
  return counts;
}

function drawRanksFromCounts(counts, n) {
  var out = [];

  for (var d = 0; d < n; d++) {
    var available = [];
    for (var r = 2; r <= 14; r++) {
      var c = counts[r] || 0;
      for (var k = 0; k < c; k++) available.push(r);
    }

    if (!available.length) break;

    var pick = available[Math.floor(Math.random() * available.length)];
    out.push(pick);
    counts[pick]--;
  }

  return out;
}

function dealFromSeed(seed, drawCount) {
  var base = Array.isArray(seed) ? seed.slice() : [];
  var need = Math.max(0, 5 - base.length);

  if (drawCount !== undefined && drawCount !== null) {
    need = Math.max(need, drawCount);
  }

  var counts = buildRankOnlyDeckCounts();

  for (var i = 0; i < base.length; i++) {
    var r = Number(base[i]);
    if (counts[r] === undefined) continue;
    counts[r] = Math.max(0, counts[r] - 1);
  }

  var drawn = drawRanksFromCounts(counts, need);
  return base.concat(drawn).slice(0, 5).sort(function(a, b) { return a - b; });
}

function intRankToChar(v) {
  if (v >= 2 && v <= 9) return String(v);
  if (v === 10) return 'T';
  if (v === 11) return 'J';
  if (v === 12) return 'Q';
  if (v === 13) return 'K';
  if (v === 14) return 'A';
  return '?';
}

function intHandToCards(intHand) {
  if (!Array.isArray(intHand)) return [];
  return intHand.map(function(v) {
    return intRankToChar(Number(v));
  });
}

/* 2-7 lowball hand evaluator */
function intIsStraight(vals) {
  var sv = [], seen = {};
  for (var i = 0; i < vals.length; i++) {
    if (!seen[vals[i]]) { sv.push(vals[i]); seen[vals[i]] = true; }
  }
  sv.sort(function(a, b) { return a - b; });
  if (sv.length < 5) return false;
  for (var j = 0; j <= sv.length - 5; j++) {
    if (sv[j + 4] - sv[j] === 4) return true;
  }
  return false;
}

function intClassify27(hand) {
  var counts = {};
  for (var i = 0; i < hand.length; i++) counts[hand[i]] = (counts[hand[i]] || 0) + 1;
  var freq = [];
  for (var k in counts) freq.push(counts[k]);
  freq.sort(function(a, b) { return b - a; });
  var sorted_desc = hand.slice().sort(function(a, b) { return b - a; });

  if (freq[0] === 4) return [6, sorted_desc];
  if (freq[0] === 3 && freq.length >= 2 && freq[1] === 2) return [5, sorted_desc];
  if (intIsStraight(hand) && freq[0] === 1) return [4, sorted_desc];
  if (freq[0] === 3) return [3, sorted_desc];
  var pc = 0;
  for (var p = 0; p < freq.length; p++) { if (freq[p] === 2) pc++; }
  if (pc === 2) return [2, sorted_desc];
  if (freq[0] === 2) return [1, sorted_desc];
  return [0, sorted_desc];
}

function intCompare27(h1, h2) {
  var c1 = intClassify27(h1), c2 = intClassify27(h2);
  if (c1[0] < c2[0]) return -1;
  if (c1[0] > c2[0]) return 1;
  for (var i = 0; i < c1[1].length; i++) {
    if (c1[1][i] < c2[1][i]) return -1;
    if (c1[1][i] > c2[1][i]) return 1;
  }
  return 0;
}

/* bucket labels */
function intBucketLabel(hand) {
  var cl = intClassify27(hand), cat = cl[0];

  var counts = {};
  for (var i = 0; i < hand.length; i++) counts[hand[i]] = (counts[hand[i]] || 0) + 1;

  if (cat >= 2) return 'Straight';

  if (cat === 1) {
    var pr = 0;
    for (var r in counts) { if (counts[r] === 2) pr = Math.max(pr, +r); }
    if (pr >= 2 && pr <= 9) return '' + pr + pr;
    return 'Straight';
  }

  var s = hand.slice().sort(function(a, b) { return a - b; });
  var hi = s[4], sh = s[3];

  if (hi === 7) return sh <= 5 ? '75' : '76';
  if (hi === 8) {
    if (sh === 5) return '85';
    if (sh === 6) return '86';
    return '87';
  }
  if (hi === 9) {
    if (sh === 5) return '95';
    if (sh === 6) return '96';
    if (sh === 7) return '97';
    return '98';
  }
  if (hi === 10) {
    if (sh <= 5) return 'T5';
    if (sh === 6) return 'T6';
    if (sh === 7) return 'T7';
    if (sh === 8) return 'T8';
    return 'T9';
  }
  if (hi === 11) return sh <= 8 ? 'J8' : 'J9';
  if (hi === 12) return 'Q';
  if (hi === 13) return 'K';
  return 'A';
}

function intDescribe27(hand) {
  var cl = intClassify27(hand), cat = cl[0];
  var names = ['High Card', 'Pair', 'Two Pair', 'Trips', 'Straight', 'Full House', 'Quads'];
  if (cat === 0) {
    var s = hand.slice().sort(function(a, b) { return b - a; });
    var rmap = {2:'2',3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'T',11:'J',12:'Q',13:'K',14:'A'};
    return s.map(function(v) { return rmap[v] || '?'; }).join('-') + ' low';
  }
  return names[cat] || '?';
}

/* no limit bet sizing */
function nlBetAmount(frac, pot, invested, stack) {
  if (frac === 'allin') return stack - invested;
  var amt = frac * pot;
  return Math.min(amt, stack - invested);
}

/* random hand dealing for nl */
function dealNLHand(seedData, position) {
  var seeds5 = seedData[position + '_5'] || [];
  var seeds4 = seedData[position + '_4'] || [];
  var seeds3 = seedData[position + '_3'] || [];

  var options = [];
  seeds5.forEach(function(s) { options.push({ seed: s, draw: 0 }); });
  seeds4.forEach(function(s) { options.push({ seed: s, draw: 1 }); });
  seeds3.forEach(function(s) { options.push({ seed: s, draw: 2 }); });

  if (options.length === 0) return [2, 3, 4, 5, 7];

  var pick = options[Math.floor(Math.random() * options.length)];
  if (pick.draw === 0) {
    return pick.seed.slice().sort(function(a, b) { return a - b; });
  }
  return dealFromSeed(pick.seed, pick.draw);
}

/* game engine */
function GameEngine(humanPos, mode, potSize) {
  this.humanPos = humanPos || 'BB';
  this.mode = mode || GAME_MODE;
  this.cardRemovalCount = 0;
  this.phase = PHASE_BET;
  this.over = false;
  this.winner = null;
  this.historyStr = '';
  this.isNL = (this.mode === 'nl');
  this.lastBetAction = '';

  var seedData = SEEDS[this.mode] || SEEDS['1draw'];
  var drawCount = seedData.draw_count || 1;

  var btnIntHand, bbIntHand;

  if (this.isNL) {
    btnIntHand = dealNLHand(seedData, 'btn');
    bbIntHand = dealNLHand(seedData, 'bb');
  } else {
    var btnSeed = seedData.btn[Math.floor(Math.random() * seedData.btn.length)];
    var bbSeed = seedData.bb[Math.floor(Math.random() * seedData.bb.length)];
    btnIntHand = dealFromSeed(btnSeed, drawCount);
    bbIntHand = dealFromSeed(bbSeed, drawCount);
  }

  this.pot = potSize || GAME_POT;
  this.startPot = this.pot;
  this.actor = 'BB';
  this.toCall = 0;
  this.raisesUsed = 0;
  this.allIn = false;

  this.pl = {
    BTN: { hand: intHandToCards(btnIntHand), intHand: btnIntHand, invested: 0, folded: false },
    BB:  { hand: intHandToCards(bbIntHand),  intHand: bbIntHand,  invested: 0, folded: false }
  };
}

GameEngine.prototype.opp = function(pos) {
  return pos === 'BTN' ? 'BB' : 'BTN';
};

GameEngine.prototype.legalActions = function() {
  if (this.over) return [];
  if (this.isNL) return this._nlLegal();
  return this._limitLegal();
};

GameEngine.prototype._limitLegal = function() {
  if (this.toCall === 0) return ['check', 'bet'];
  var acts = ['fold', 'call'];
  if (this.raisesUsed < LIMIT_MAX_RAISES) acts.push('raise');
  return acts;
};

GameEngine.prototype._nlLegal = function() {
  var me = this.pl[this.actor];
  var remaining = NL_STACK - me.invested;
  if (remaining <= 0) return [];

  if (this.allIn) {
    var acts = ['fold'];
    if (this.toCall <= remaining) acts.push('call');
    return acts;
  }

  if (this.toCall === 0) {
    var acts = ['check'];
    var betActions = ['b40', 'b80', 'b120', 'ba'];
    for (var i = 0; i < betActions.length; i++) {
      var ba = betActions[i];
      var frac = NL_BET_FRACS[ba];
      var amt = nlBetAmount(frac, this.pot, me.invested, NL_STACK);
      if (amt > 0) acts.push(ba);
    }
    return acts;
  }

  var acts = ['fold'];
  if (this.toCall <= remaining) acts.push('call');

  var raiseOpts = NL_RAISE_OPTIONS[this.lastBetAction] || {};
  for (var ra in raiseOpts) {
    var frac = raiseOpts[ra];
    if (frac === 'allin') {
      var cost = NL_STACK - me.invested;
      if (cost > this.toCall) acts.push(ra);
    } else {
      var potAfterCall = this.pot + this.toCall;
      var raiseAmt = frac * potAfterCall;
      var totalCost = this.toCall + raiseAmt;
      if (totalCost <= remaining && raiseAmt > 0) acts.push(ra);
    }
  }
  return acts;
};

GameEngine.prototype.apply = function(action) {
  if (this.over) return;
  if (this.isNL) {
    this._nlApply(action);
  } else {
    this._limitApply(action);
  }
  this._appendHistory(action);
  this._checkAutoTerminal();
};

GameEngine.prototype._appendHistory = function(action) {
  var map = {
    'check': 'k', 'bet': 'b', 'call': 'c', 'fold': 'f', 'raise': 'r',
    'b40': 'b40', 'b80': 'b80', 'b120': 'b120', 'ba': 'ba',
    'r86': 'r86', 'r111': 'r111', 'ra': 'ra'
  };
  this.historyStr += (map[action] || action);
};

GameEngine.prototype._checkAutoTerminal = function() {
  if (!this.over && this.historyStr.endsWith('kk')) {
    this.over = true;
    this.phase = PHASE_SHOWDOWN;
    this._doShowdown();
  }
};

GameEngine.prototype._limitApply = function(action) {
  var me = this.pl[this.actor];
  var oppPos = this.opp(this.actor);
  var them = this.pl[oppPos];

  if (action === 'fold') {
    me.folded = true;
    this.over = true;
    this.winner = oppPos;
  } else if (action === 'check') {
    this.actor = oppPos;
  } else if (action === 'call') {
    var amt = this.toCall;
    me.invested += amt;
    this.pot += amt;
    this.toCall = 0;
    this.over = true;
    this.phase = PHASE_SHOWDOWN;
    this._doShowdown();
  } else if (action === 'bet') {
    var amt = LIMIT_RAISE_SCHEDULE[0];
    me.invested += amt;
    this.pot += amt;
    this.toCall = amt;
    this.raisesUsed = 0;
    this.actor = oppPos;
  } else if (action === 'raise') {
    var newlvl = LIMIT_RAISE_SCHEDULE[this.raisesUsed + 1];
    var add = newlvl - me.invested;
    me.invested += add;
    this.pot += add;
    this.toCall = newlvl - them.invested;
    this.raisesUsed++;
    this.actor = oppPos;
  }
};

GameEngine.prototype._nlApply = function(action) {
  var me = this.pl[this.actor];
  var oppPos = this.opp(this.actor);
  var them = this.pl[oppPos];

  if (action === 'check') {
    this.actor = oppPos;
  } else if (action === 'fold') {
    me.folded = true;
    this.over = true;
    this.winner = oppPos;
  } else if (action === 'call') {
    var callAmt = Math.min(this.toCall, NL_STACK - me.invested);
    me.invested += callAmt;
    this.pot += callAmt;
    this.toCall = 0;
    this.over = true;
    this.phase = PHASE_SHOWDOWN;
    this._doShowdown();
  } else if (NL_BET_FRACS[action] !== undefined) {
    var frac = NL_BET_FRACS[action];
    var betAmt = Math.max(nlBetAmount(frac, this.pot, me.invested, NL_STACK), 0);
    me.invested += betAmt;
    this.pot += betAmt;
    this.toCall = me.invested - them.invested;
    this.lastBetAction = action;
    this.actor = oppPos;
    if (me.invested >= NL_STACK) this.allIn = true;
  } else {
    var raiseOpts = NL_RAISE_OPTIONS[this.lastBetAction] || {};
    var frac = raiseOpts[action] || 'allin';
    var totalAdd;
    if (frac === 'allin') {
      totalAdd = NL_STACK - me.invested;
    } else {
      var potAfterCall = this.pot + this.toCall;
      var raiseAmt = frac * potAfterCall;
      totalAdd = Math.min(this.toCall + raiseAmt, NL_STACK - me.invested);
    }
    me.invested += totalAdd;
    this.pot += totalAdd;
    this.toCall = me.invested - them.invested;
    this.lastBetAction = action;
    this.actor = oppPos;
    if (me.invested >= NL_STACK) this.allIn = true;
  }
};

GameEngine.prototype._doShowdown = function() {
  var cmp = intCompare27(this.pl.BTN.intHand, this.pl.BB.intHand);
  if (cmp < 0) this.winner = 'BTN';
  else if (cmp > 0) this.winner = 'BB';
  else this.winner = 'TIE';
  this.over = true;
  this.phase = PHASE_SHOWDOWN;
};

GameEngine.prototype.payoff = function(pos) {
  if (!this.over) return 0;
  var p = this.pl[pos];
  if (this.winner === 'TIE') return (this.pot / 2) - p.invested;
  if (this.winner === pos) return this.pot - p.invested;
  return -p.invested;
};

GameEngine.prototype.getSolverKey = function() {
  return this.historyStr;
};

GameEngine.prototype.getBucket = function(pos) {
  return intBucketLabel(this.pl[pos].intHand);
};

GameEngine.prototype.getHandDescription = function(pos) {
  return intDescribe27(this.pl[pos].intHand);
};

GameEngine.prototype.getBetInfo = function() {
  if (this.isNL) {
    var me = this.pl[this.actor];
    var info = { toCall: this.toCall, isNL: true };
    info.b40 = Math.round(nlBetAmount(0.40, this.pot, me.invested, NL_STACK) * 10) / 10;
    info.b80 = Math.round(nlBetAmount(0.80, this.pot, me.invested, NL_STACK) * 10) / 10;
    info.b120 = Math.round(nlBetAmount(1.20, this.pot, me.invested, NL_STACK) * 10) / 10;
    info.ba = Math.round((NL_STACK - me.invested) * 10) / 10;

    var raiseOpts = NL_RAISE_OPTIONS[this.lastBetAction] || {};
    if (raiseOpts.r86) {
      var pac = this.pot + this.toCall;
      info.r86 = Math.round((this.toCall + 0.86 * pac) * 10) / 10;
    }
    if (raiseOpts.r111) {
      var pac = this.pot + this.toCall;
      info.r111 = Math.round((this.toCall + 1.11 * pac) * 10) / 10;
    }
    info.ra = Math.round((NL_STACK - me.invested) * 10) / 10;
    return info;
  }
  var nextBet = LIMIT_RAISE_SCHEDULE[0];
  var nextRaise = this.raisesUsed < LIMIT_MAX_RAISES ? LIMIT_RAISE_SCHEDULE[this.raisesUsed + 1] : 0;
  return {
    toCall: this.toCall,
    betSize: nextBet,
    raiseSize: nextRaise,
    raisesLeft: LIMIT_MAX_RAISES - this.raisesUsed,
    isNL: false
  };
};