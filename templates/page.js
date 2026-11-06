// 书脉 · 书房页. Everything below is built from the JSON in #bk-data, so the
// page is one file with no build step. Text always goes in through
// textContent, never innerHTML.
(function () {
  "use strict";

  var D = JSON.parse(document.getElementById("bk-data").textContent);
  var THEME = document.documentElement.getAttribute("data-theme") || "yutu";
  var SVGNS = "http://www.w3.org/2000/svg";
  var app = document.getElementById("bk-app");

  // ------------------------------------------------------------ helpers

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function sv(tag, attrs, text) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs || {}) {
      if (attrs[k] !== undefined && attrs[k] !== null) n.setAttribute(k, attrs[k]);
    }
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function f1(v) {
    return (Math.round(v * 10) / 10).toFixed(1);
  }
  function fmtHours(h) {
    return h >= 10 ? String(Math.round(h)) : f1(h);
  }
  function fmtNum(v) {
    return String(Math.round(v * 10) / 10);
  }
  function fmtCount(n) {
    if (n >= 10000) return { value: String(Math.round(n / 1000) / 10).replace(/\.0$/, "") + "万", unit: "条" };
    return { value: String(Math.round(n)), unit: "条" };
  }
  function monthLabel(m) {
    return m.slice(0, 4) + " 年 " + Number(m.slice(5, 7)) + " 月";
  }
  function maxOf(arr, key) {
    return arr.reduce(function (a, x) { return Math.max(a, x[key]); }, 0) || 1;
  }
  // Deterministic PRNG (mulberry32) so the map and sky never reshuffle.
  function seeded(seed) {
    return function () {
      seed = (seed + 0x6d2b79f5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  // Rough text width: CJK and full-width glyphs are 1em, the rest about 0.58em.
  function measure(text, px) {
    var w = 0;
    for (var i = 0; i < text.length; i++) {
      var c = text.charCodeAt(i);
      w += c > 0x2e7f ? 1 : c >= 65 && c <= 90 ? 0.68 : 0.56;
    }
    return w * px;
  }

  var books = D.books || [];
  var topics = D.topics || [];
  var stats = D.stats;

  // --------------------------------------------------------------- hero

  var hero = el("header", "bk-hero");
  hero.append(el("p", "bk-overline", "Reading · 微信读书"), el("h1", null, D.title || "书房"));
  app.append(hero);

  // ---------------------------------------------------------- stats band

  (function () {
    var items = [];
    if (stats) {
      items.push({ value: String(Math.round(stats.totalHours)), unit: "小时", label: "累计阅读" });
      if (stats.readDays) items.push({ value: String(stats.readDays), unit: "天", label: "有阅读的日子" });
      items.push({ value: String(stats.readBooks), unit: "本", label: "读过" });
      items.push({ value: String(stats.finishedBooks), unit: "本", label: "读完" });
      var c = fmtCount(stats.notes);
      items.push({ value: c.value, unit: c.unit, label: "划线和想法" });
    } else {
      var hours = books.reduce(function (a, b) { return a + b.hours; }, 0);
      var notes = books.reduce(function (a, b) { return a + b.marks + b.thoughtCount; }, 0);
      items.push({ value: fmtHours(hours), unit: "小时", label: "累计阅读" });
      items.push({ value: String(books.length), unit: "本", label: "有笔记的书" });
      items.push({ value: String(books.filter(function (b) { return b.finished; }).length), unit: "本", label: "读完" });
      var n = fmtCount(notes);
      items.push({ value: n.value, unit: n.unit, label: "划线和想法" });
    }
    var band = el("section", "bk-stats");
    band.setAttribute("aria-label", "阅读总览");
    items.forEach(function (s) {
      var box = el("div", "bk-stat");
      var v = el("p", "bk-stat-value", s.value);
      v.append(el("span", null, s.unit));
      box.append(v, el("p", "bk-stat-label", s.label));
      band.append(box);
    });
    app.append(band);
  })();

  function bar(cls, heightPct, tip, label) {
    var b = el("div", "bk-bar" + (cls ? " " + cls : ""));
    b.style.height = heightPct + "%";
    b.tabIndex = 0;
    b.setAttribute("data-tip", tip);
    b.setAttribute("aria-label", label);
    return b;
  }
  function panelSection(extra) {
    var sec = el("section", "bk-section");
    var panel = el("div", "bk-panel" + (extra ? " " + extra : ""));
    sec.append(panel);
    return { sec: sec, panel: panel };
  }

  // -------------------------------------------------------------- charts

  if (stats && stats.years.length) {
    var curYear = Number((stats.generatedAt || "").slice(0, 4));
    var asOf = stats.generatedAt ? Number(stats.generatedAt.slice(5, 7)) + " 月 " + Number(stats.generatedAt.slice(8, 10)) + " 日" : "";
    var maxYear = maxOf(stats.years, "hours");
    var ys = panelSection();
    var yc = el("div", "bk-year-chart");
    yc.setAttribute("role", "group");
    yc.setAttribute("aria-label", "每年阅读时长");
    stats.years.forEach(function (y) {
      var col = el("div", "bk-year-col");
      var v = el("span", "bk-year-value", fmtHours(y.hours));
      v.append(el("small", null, "h"));
      var track = el("div", "bk-year-track");
      var partial = y.year === curYear;
      track.append(bar(partial ? "is-partial" : "", Math.max((y.hours / maxYear) * 100, 1.5),
        y.year + " 年" + (partial && asOf ? "截至 " + asOf : "") + "｜" + fmtNum(y.hours) + " 小时｜" + y.days + " 天在读｜读完 " + y.finished + " 本",
        y.year + " 年 " + fmtNum(y.hours) + " 小时，" + y.days + " 天在读，读完 " + y.finished + " 本"));
      col.append(v, track, el("span", "bk-axis-label", String(y.year)));
      yc.append(col);
    });
    ys.panel.append(yc);
    app.append(ys.sec);
  }

  if (stats && stats.months.length) {
    var first = stats.months.findIndex(function (m) { return m.hours > 0; });
    var months = stats.months.slice(Math.max(first, 0));
    var maxMonth = maxOf(months, "hours");
    var peakMonth = months.reduce(function (a, b) { return b.hours > a.hours ? b : a; });
    var ms = panelSection();
    var mc = el("div", "bk-month-chart");
    mc.setAttribute("role", "group");
    mc.setAttribute("aria-label", "每月阅读时长");
    var ma = el("div", "bk-month-axis");
    ma.setAttribute("aria-hidden", "true");
    months.forEach(function (m) {
      var col = el("div", "bk-month-col");
      col.append(bar(m.month === peakMonth.month ? "is-peak" : "", Math.max((m.hours / maxMonth) * 100, m.hours > 0 ? 2 : 0.6),
        monthLabel(m.month) + "｜" + fmtNum(m.hours) + " 小时", monthLabel(m.month) + " " + fmtNum(m.hours) + " 小时"));
      mc.append(col);
      ma.append(el("span", null, m.month.slice(5) === "01" || m === months[0] ? m.month.slice(0, 4) : ""));
    });
    ms.panel.append(mc, ma);
    app.append(ms.sec);
  }

  if (stats && stats.hourly.length === 24) {
    var maxHour = maxOf(stats.hourly, "hours");
    var peakHour = stats.hourly.reduce(function (a, b) { return b.hours > a.hours ? b : a; });
    var hs = panelSection();
    var hc = el("div", "bk-hour-chart");
    hc.setAttribute("role", "group");
    hc.setAttribute("aria-label", "按小时的累计阅读时长");
    var ha = el("div", "bk-hour-axis");
    ha.setAttribute("aria-hidden", "true");
    stats.hourly.forEach(function (x) {
      var col = el("div", "bk-hour-col");
      col.append(bar(x.hour === peakHour.hour ? "is-peak" : "", Math.max((x.hours / maxHour) * 100, 1.5),
        x.hour + ":00–" + (x.hour + 1) + ":00｜累计 " + fmtNum(x.hours) + " 小时", x.hour + " 点 累计 " + fmtNum(x.hours) + " 小时"));
      hc.append(col);
      ha.append(el("span", null, x.hour % 6 === 0 ? x.hour + " 点" : ""));
    });
    hs.panel.append(hc, ha);
    app.append(hs.sec);
  }

  if (stats && stats.categories.length) {
    var cats = stats.categories;
    var two = el("div", "bk-two");
    if (cats.length >= 3) {
      var radarCats = cats.slice(0, 6);
      var radarMax = maxOf(radarCats, "hours");
      var R = { cx: 210, cy: 136, r: 84 };
      var pt = function (i, frac) {
        var a = -Math.PI / 2 + (i * 2 * Math.PI) / radarCats.length;
        return { x: R.cx + frac * R.r * Math.cos(a), y: R.cy + frac * R.r * Math.sin(a) };
      };
      var ring = function (frac) {
        return radarCats.map(function (_, i) { var p = pt(i, frac); return p.x.toFixed(1) + "," + p.y.toFixed(1); }).join(" ");
      };
      var rs = panelSection("bk-radar");
      var svg = sv("svg", {
        viewBox: "0 0 420 272",
        role: "group",
        "aria-label": "阅读偏好：" + radarCats.map(function (c) { return c.name + " " + fmtNum(c.hours) + " 小时"; }).join("，"),
      });
      [0.25, 0.5, 0.75, 1].forEach(function (f) { svg.append(sv("polygon", { class: "bk-radar-ring", points: ring(f) })); });
      radarCats.forEach(function (_, i) {
        var p = pt(i, 1);
        svg.append(sv("line", { class: "bk-radar-axis", x1: R.cx, y1: R.cy, x2: p.x.toFixed(1), y2: p.y.toFixed(1) }));
      });
      var verts = radarCats.map(function (c, i) { return pt(i, Math.max(c.hours / radarMax, 0.06)); });
      svg.append(sv("polygon", { class: "bk-radar-shape", points: verts.map(function (v) { return v.x.toFixed(1) + "," + v.y.toFixed(1); }).join(" ") }));
      verts.forEach(function (v, i) {
        var c = radarCats[i];
        var g = sv("g", { class: "bk-radar-pt", tabindex: "0", "data-tip": c.name + "｜" + fmtNum(c.hours) + " 小时｜" + c.count + " 本", "aria-label": c.name + " " + fmtNum(c.hours) + " 小时，" + c.count + " 本" });
        g.append(sv("circle", { class: "bk-radar-hit", cx: v.x.toFixed(1), cy: v.y.toFixed(1), r: 13 }));
        g.append(sv("circle", { class: "bk-radar-dot", cx: v.x.toFixed(1), cy: v.y.toFixed(1), r: 4.5 }));
        svg.append(g);
      });
      radarCats.forEach(function (c, i) {
        var p = pt(i, 1.2);
        var anchor = Math.abs(p.x - R.cx) < 4 ? "middle" : p.x > R.cx ? "start" : "end";
        var t = sv("text", { class: "bk-radar-label", x: p.x.toFixed(1), y: p.y.toFixed(1), "text-anchor": anchor, "dominant-baseline": "middle", "aria-hidden": "true" });
        t.append(sv("tspan", {}, c.name));
        t.append(sv("tspan", { class: "bk-radar-value", dx: 5 }, fmtNum(c.hours) + "h"));
        svg.append(t);
      });
      rs.panel.append(svg);
      two.append(rs.sec);
    } else {
      two.classList.add("is-single");
    }
    var maxCat = maxOf(cats, "hours");
    var cs = panelSection("bk-cats");
    cats.forEach(function (c, i) {
      var row = el("div", "bk-cat-row");
      row.tabIndex = 0;
      row.setAttribute("data-tip", c.name + "｜" + fmtNum(c.hours) + " 小时｜" + c.count + " 本");
      var track = el("div", "bk-cat-track");
      var b = el("div", "bk-cat-bar" + (i === 0 ? " is-peak" : ""));
      b.style.width = Math.max((c.hours / maxCat) * 100, 2) + "%";
      track.append(b);
      row.append(el("span", "bk-cat-name", c.name), track, el("span", "bk-cat-value", fmtNum(c.hours) + "h · " + c.count + " 本"));
      cs.panel.append(row);
    });
    two.append(cs.sec);
    app.append(two);
  }

  // ------------------------------------------------------- knowledge map

  var MAP = { colGap: 150, rowGap: 74, pad: 44, gap: 26, band: 104, minW: 960, label: 13, line: 16 };

  function wrapLabel(name, maxW) {
    if (measure(name, MAP.label) <= maxW) return [name];
    var chars = Array.from(name);
    // Two balanced lines when they fit, avoiding a break inside a Latin word or number.
    var best = -1, bestCost = Infinity;
    for (var k = 1; k < chars.length; k++) {
      var w1 = measure(chars.slice(0, k).join(""), MAP.label), w2 = measure(chars.slice(k).join(""), MAP.label);
      if (w1 > maxW || w2 > maxW) continue;
      var cost = Math.abs(w1 - w2) + (/[A-Za-z0-9]/.test(chars[k - 1]) && /[A-Za-z0-9]/.test(chars[k]) ? 60 : 0);
      if (cost < bestCost) { best = k; bestCost = cost; }
    }
    if (best > 0) return [chars.slice(0, best).join(""), chars.slice(best).join("")];
    var a = "";
    var i = 0;
    while (i < chars.length && measure(a + chars[i], MAP.label) <= maxW) a += chars[i++];
    var b = chars.slice(i).join("");
    if (measure(b, MAP.label) > maxW) {
      var t = "";
      for (var k = i; k < chars.length; k++) {
        if (measure(t + chars[k] + "…", MAP.label) > maxW) break;
        t += chars[k];
      }
      b = t + "…";
    }
    return [a, b];
  }

  // Lay out domains as regions on a grid and topics as cities inside them.
  // Every region is measured first (coast, domain label, city labels), then
  // the grid takes the widest region per column and the tallest per row, so
  // regions cannot overlap each other, the frame or the compass band.
  function layoutMap() {
    var doms = D.domains.filter(function (d) {
      return topics.some(function (t) { return t.domain === d.name; });
    });
    var n = doms.length;
    if (!n) return null;
    var gcols = n <= 3 ? n : n === 4 ? 2 : 3;
    var grows = Math.ceil(n / gcols);
    var cities = topics.map(function (t, i) {
      return { t: t, i: i, x: 0, y: 0, r: Math.min(3.6 + 1.5 * Math.sqrt(t.books.length), 9.5), lines: [t.name] };
    });

    var regions = doms.map(function (d, di) {
      var members = cities.filter(function (c) { return c.t.domain === d.name; });
      var m = members.length;
      var tcols = m === 1 ? 1 : gcols <= 2 && m >= 5 ? 3 : 2;
      var trows = Math.ceil(m / tcols);
      var rand = seeded(di + 7);
      members.forEach(function (c, k) {
        var row = Math.floor(k / tcols);
        var col = k % tcols;
        var inRow = Math.min(tcols, m - row * tcols);
        var stagger = trows > 1 ? (row % 2 ? 14 : -14) : 0;
        c.x = (col - (inRow - 1) / 2) * MAP.colGap + stagger + (rand() - 0.5) * 16;
        c.y = (row - (trows - 1) / 2) * MAP.rowGap + (rand() - 0.5) * 12;
        c.lines = wrapLabel(c.t.name, MAP.colGap - 34);
      });
      var rx = ((tcols - 1) * MAP.colGap) / 2 + (tcols === 1 ? 88 : 74);
      var ry = ((trows - 1) * MAP.rowGap) / 2 + 62;
      var phase = [rand() * 6.28, rand() * 6.28, rand() * 6.28];
      var reg = { d: d, members: members, rx: rx, ry: ry, phase: phase, cx: 0, cy: 0 };
      reg.labelY = 6 - ry * 1.1 - 12;
      reg.labelW = measure(d.name, 19) * 1.32 + 10 + measure(d.books + " 本", 12) * 1.1;
      var L = Infinity, Rt = -Infinity, T = Infinity, B = -Infinity;
      var grow = function (x0, y0, x1, y1) {
        L = Math.min(L, x0); Rt = Math.max(Rt, x1); T = Math.min(T, y0); B = Math.max(B, y1);
      };
      outline(reg, 1.15).forEach(function (p) { grow(p.x, p.y, p.x, p.y); });
      grow(-reg.labelW / 2, reg.labelY - 20, reg.labelW / 2, reg.labelY + 6);
      members.forEach(function (c) {
        var w = Math.max.apply(null, c.lines.map(function (s) { return measure(s, MAP.label); }));
        var top = c.y + c.r + 15 - 13;
        grow(c.x - w / 2 - 4, Math.min(c.y - 22, top), c.x + w / 2 + 4, c.y + c.r + 15 + (c.lines.length - 1) * MAP.line + 5);
        grow(c.x - 22, c.y - 22, c.x + 22, c.y + 22);
      });
      reg.ext = { L: L, R: Rt, T: T, B: B, w: Rt - L, h: B - T };
      return reg;
    });

    var cw = [], rh = [];
    regions.forEach(function (r, di) {
      var c = di % gcols, row = Math.floor(di / gcols);
      cw[c] = Math.max(cw[c] || 0, r.ext.w);
      rh[row] = Math.max(rh[row] || 0, r.ext.h);
    });
    var sum = function (a, k) { var s = 0; for (var i = 0; i < k; i++) s += a[i]; return s; };
    var gridW = sum(cw, gcols) + MAP.gap * (gcols - 1);
    var W = Math.ceil(Math.max(MAP.minW, gridW + 2 * MAP.pad));
    var x0 = (W - gridW) / 2;
    var y = MAP.pad;
    for (var row = 0; row < grows; row++) {
      var inRow = regions.slice(row * gcols, row * gcols + gcols);
      var rowW = sum(cw, inRow.length) + MAP.gap * (inRow.length - 1);
      var off = (gridW - rowW) / 2;
      inRow.forEach(function (r, c) {
        var cellX = x0 + off + sum(cw, c) + MAP.gap * c;
        var slack = rh[row] - r.ext.h;
        var nudge = Math.min(14, slack / 2) * (c % 2 ? 1 : -1);
        r.cx = cellX + (cw[c] - r.ext.w) / 2 - r.ext.L;
        r.cy = y + slack / 2 - r.ext.T + nudge;
      });
      y += rh[row] + MAP.gap;
    }
    var H = Math.ceil(y - MAP.gap + MAP.band);
    regions.forEach(function (r) {
      r.members.forEach(function (c) { c.x += r.cx; c.y += r.cy; });
    });

    var roads = [];
    cities.forEach(function (a) {
      cities.forEach(function (b) {
        if (b.i <= a.i) return;
        var w = a.t.books.filter(function (x) { return b.t.books.indexOf(x) >= 0; }).length;
        var sea = a.t.domain !== b.t.domain;
        if (!(w >= 2 || (w === 1 && !sea))) return;
        var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        var bend = sea ? 0.18 : 0.08;
        var qx = mx - (b.y - a.y) * bend, qy = my + (b.x - a.x) * bend;
        roads.push({ a: a, b: b, w: w, sea: sea, d: "M" + a.x.toFixed(1) + "," + a.y.toFixed(1) + "Q" + qx.toFixed(1) + "," + qy.toFixed(1) + " " + b.x.toFixed(1) + "," + b.y.toFixed(1) });
      });
    });
    return { W: W, H: H, regions: regions, cities: cities, roads: roads };
  }

  // A wobbly ellipse around a region, in absolute coordinates once cx/cy are set.
  function outline(r, scale) {
    var pts = [];
    for (var k = 0; k < 40; k++) {
      var a = (k / 40) * Math.PI * 2;
      var wob = 1 + 0.07 * Math.sin(3 * a + r.phase[0]) + 0.05 * Math.sin(5 * a + r.phase[1]) + 0.025 * Math.sin(9 * a + r.phase[2]);
      pts.push({ x: r.cx + Math.cos(a) * r.rx * wob * scale, y: r.cy + 6 + Math.sin(a) * r.ry * wob * scale });
    }
    return pts;
  }
  // Closed Catmull-Rom spline through the outline points, written as cubic Béziers.
  function spline(pts) {
    var p = function (k) { return pts[(k + pts.length) % pts.length]; };
    var d = "M" + pts[0].x.toFixed(1) + "," + pts[0].y.toFixed(1);
    for (var k = 0; k < pts.length; k++) {
      var p0 = p(k - 1), p1 = p(k), p2 = p(k + 1), p3 = p(k + 2);
      d += "C" + (p1.x + (p2.x - p0.x) / 6).toFixed(1) + "," + (p1.y + (p2.y - p0.y) / 6).toFixed(1) + " " +
        (p2.x - (p3.x - p1.x) / 6).toFixed(1) + "," + (p2.y - (p3.y - p1.y) / 6).toFixed(1) + " " +
        p2.x.toFixed(1) + "," + p2.y.toFixed(1);
    }
    return d + "Z";
  }

  function regionLabel(r, size) {
    var t = sv("text", { class: "bk-region-label", x: r.cx.toFixed(1), y: (r.cy + r.labelY).toFixed(1), "text-anchor": "middle", "aria-hidden": "true" }, r.d.name);
    t.append(sv("tspan", { class: "bk-region-count", dx: size || 8 }, r.d.books + " 本"));
    return t;
  }
  function cityLabel(c) {
    var t = sv("text", { class: "bk-city-label", x: c.x.toFixed(1), y: (c.y + c.r + 15).toFixed(1), "text-anchor": "middle" });
    c.lines.forEach(function (line, k) {
      t.append(sv("tspan", { x: c.x.toFixed(1), dy: k ? MAP.line : 0 }, line));
    });
    return t;
  }
  function cityGroup(c) {
    var g = sv("g", {
      class: "bk-city",
      "data-topic": c.i,
      tabindex: "0",
      role: "button",
      "aria-label": c.t.name + "，" + c.t.books.length + " 本书",
      "data-tip": c.t.name + "｜" + c.t.books.length + " 本书｜≥ " + fmtNum(c.t.hours) + " 小时",
    });
    g.append(sv("circle", { class: "bk-city-hit", cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: 20 }));
    g.append(sv("circle", { class: "bk-city-focus", cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: (c.r + 7).toFixed(1) }));
    return g;
  }
  function roadPaths(L, group) {
    L.roads.forEach(function (e) {
      group.append(sv("path", {
        class: "bk-road" + (e.sea ? " is-sea" : ""),
        d: e.d,
        "data-a": e.a.i,
        "data-b": e.b.i,
        style: "stroke-width:" + Math.min(0.8 + 0.55 * e.w, 3.4).toFixed(2),
      }));
    });
    L.roads.forEach(function (e) {
      group.append(sv("path", { class: "bk-road-hit", d: e.d, "data-tip": e.a.t.name + " · " + e.b.t.name + "｜共读 " + e.w + " 本" }));
    });
  }
  // Legend rows only for the kinds of road the map actually has.
  function legend(L, x) {
    var kinds = [[false, "同领域共读的书"], [true, "跨领域共读的书"]].filter(function (k) {
      return L.roads.some(function (e) { return e.sea === k[0]; });
    });
    var g = sv("g", { class: "bk-legend", transform: "translate(" + x + " " + (L.H - 40 - 22 * (kinds.length - 1)) + ")", "aria-hidden": "true" });
    kinds.forEach(function (k, i) {
      g.append(sv("path", { d: "M0 " + 22 * i + "h34", class: "bk-road" + (k[0] ? " is-sea" : ""), style: "stroke-width:2" }));
      g.append(sv("text", { x: 44, y: 22 * i + 4 }, k[1]));
    });
    return g;
  }

  // 舆图: islands, coasts, roads and sea routes, a compass.
  function drawYutu(svg, L) {
    var defs = sv("defs");
    var pat = sv("pattern", { id: "bk-sea", width: 46, height: 22, patternUnits: "userSpaceOnUse" });
    pat.append(sv("path", { d: "M4 13q5-5 10 0t10 0", class: "bk-wave" }));
    var clip = sv("clipPath", { id: "bk-map-clip" });
    clip.append(sv("rect", { x: 18, y: 18, width: L.W - 36, height: L.H - 36 }));
    defs.append(pat, clip);
    svg.append(defs);
    svg.append(sv("rect", { class: "bk-map-sea", x: 10, y: 10, width: L.W - 20, height: L.H - 20 }));
    svg.append(sv("rect", { class: "bk-map-frame", x: 10, y: 10, width: L.W - 20, height: L.H - 20 }));
    svg.append(sv("rect", { class: "bk-map-frame is-inner", x: 17, y: 17, width: L.W - 34, height: L.H - 34 }));
    L.regions.forEach(function (r) {
      var g = sv("g", { class: "bk-region", "clip-path": "url(#bk-map-clip)" });
      g.append(sv("path", { class: "bk-coast is-far", d: spline(outline(r, 1.15)) }));
      g.append(sv("path", { class: "bk-coast", d: spline(outline(r, 1.07)) }));
      g.append(sv("path", { class: "bk-land", d: spline(outline(r, 1)) }));
      svg.append(g);
    });
    var roads = sv("g");
    roadPaths(L, roads);
    svg.append(roads);
    L.regions.forEach(function (r) { svg.append(regionLabel(r)); });
    L.cities.forEach(function (c) {
      var g = cityGroup(c);
      g.append(sv("circle", { class: "bk-city-ring", cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: c.r.toFixed(1) }));
      g.append(sv("circle", { class: "bk-city-dot", cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: 1.9 }));
      g.append(cityLabel(c));
      svg.append(g);
    });
    var cp = sv("g", { class: "bk-compass", transform: "translate(64 " + (L.H - 58) + ") scale(0.72)", "aria-hidden": "true" });
    cp.append(sv("circle", { r: 30, class: "bk-compass-ring" }));
    cp.append(sv("circle", { r: 24, class: "bk-compass-ring is-thin" }));
    cp.append(sv("path", { d: "M0 -40 L6 0 L0 40 L-6 0 Z", class: "bk-compass-needle" }));
    cp.append(sv("path", { d: "M-40 0 L0 5 L40 0 L0 -5 Z", class: "bk-compass-needle is-light" }));
    cp.append(sv("text", { y: -46, "text-anchor": "middle", class: "bk-compass-n" }, "北"));
    svg.append(cp, legend(L, L.W - 200));
  }

  // 羊皮纸: a clean star chart. Graticule, points, thin lines, labels.
  function drawKami(svg, L) {
    var defs = sv("defs");
    var clip = sv("clipPath", { id: "bk-map-clip" });
    clip.append(sv("rect", { x: 10, y: 10, width: L.W - 20, height: L.H - 20 }));
    defs.append(clip);
    svg.append(defs);
    svg.append(sv("rect", { class: "bk-map-bg", x: 10, y: 10, width: L.W - 20, height: L.H - 20 }));
    var grat = sv("g", { "clip-path": "url(#bk-map-clip)", "aria-hidden": "true" });
    var cx = L.W / 2, cy = (L.H - MAP.band + MAP.pad) / 2;
    var maxR = Math.hypot(L.W, L.H);
    for (var rr = 110; rr < maxR; rr += 110) {
      grat.append(sv("circle", { class: "bk-grat" + (rr % 220 ? " is-dash" : ""), cx: cx.toFixed(1), cy: cy.toFixed(1), r: rr }));
    }
    for (var k = 0; k < 12; k++) {
      var a = (k / 12) * Math.PI * 2;
      grat.append(sv("line", { class: "bk-grat is-dash", x1: cx.toFixed(1), y1: cy.toFixed(1), x2: (cx + Math.cos(a) * maxR).toFixed(1), y2: (cy + Math.sin(a) * maxR).toFixed(1) }));
    }
    svg.append(grat);
    svg.append(sv("rect", { class: "bk-map-frame", x: 10, y: 10, width: L.W - 20, height: L.H - 20 }));
    var roads = sv("g");
    roadPaths(L, roads);
    svg.append(roads);
    L.regions.forEach(function (r) {
      svg.append(regionLabel(r, 10));
      var y = r.cy + r.labelY + 9;
      svg.append(sv("line", { class: "bk-region-rule", x1: (r.cx - 18).toFixed(1), x2: (r.cx + 18).toFixed(1), y1: y.toFixed(1), y2: y.toFixed(1), "aria-hidden": "true" }));
    });
    L.cities.forEach(function (c) {
      var g = cityGroup(c);
      g.append(sv("circle", { class: "bk-city-ring", cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: (c.r + 2.5).toFixed(1) }));
      g.append(sv("circle", { class: "bk-city-dot", cx: c.x.toFixed(1), cy: c.y.toFixed(1), r: (c.r * 0.5 + 1.2).toFixed(1) }));
      g.append(cityLabel(c));
      svg.append(g);
    });
    var cp = sv("g", { class: "bk-compass", transform: "translate(60 " + (L.H - 56) + ") scale(0.8)", "aria-hidden": "true" });
    cp.append(sv("line", { class: "bk-compass-line", x1: 0, y1: -30, x2: 0, y2: 30 }));
    cp.append(sv("line", { class: "bk-compass-line", x1: -30, y1: 0, x2: 30, y2: 0 }));
    cp.append(sv("circle", { class: "bk-compass-line", r: 18, fill: "none" }));
    cp.append(sv("text", { y: -38, "text-anchor": "middle", class: "bk-compass-n" }, "北"));
    svg.append(cp, legend(L, L.W - 200));
  }

  // 星空: nebulae for domains, stars for topics, constellation lines for shared books.
  function drawStars(svg, L) {
    var defs = sv("defs");
    var clip = sv("clipPath", { id: "bk-map-clip" });
    clip.append(sv("rect", { x: 10, y: 10, width: L.W - 20, height: L.H - 20, rx: 12 }));
    var blur = sv("filter", { id: "bk-nebula-blur", x: "-60%", y: "-60%", width: "220%", height: "220%" });
    blur.append(sv("feGaussianBlur", { stdDeviation: 26 }));
    var glow = sv("filter", { id: "bk-star-glow", x: "-150%", y: "-150%", width: "400%", height: "400%" });
    glow.append(sv("feGaussianBlur", { stdDeviation: 3.2 }));
    var bg = sv("radialGradient", { id: "bk-sky-grad", cx: "50%", cy: "38%", r: "75%" });
    bg.append(sv("stop", { offset: "0%", "stop-color": "#16224a" }));
    bg.append(sv("stop", { offset: "55%", "stop-color": "#0b1230" }));
    bg.append(sv("stop", { offset: "100%", "stop-color": "#050816" }));
    defs.append(clip, blur, glow, bg);
    svg.append(defs);
    svg.append(sv("rect", { class: "bk-map-bg", x: 10, y: 10, width: L.W - 20, height: L.H - 20, rx: 12, fill: "url(#bk-sky-grad)" }));
    var sky = sv("g", { "clip-path": "url(#bk-map-clip)", "aria-hidden": "true" });
    var rand = seeded(L.W * 7 + L.H);
    var count = Math.round((L.W * L.H) / 2600);
    for (var i = 0; i < count; i++) {
      var big = rand() > 0.93;
      var op = big ? 0.55 + rand() * 0.35 : 0.15 + rand() * 0.4;
      sky.append(sv("circle", {
        class: "bk-bgstar" + (big ? " is-twinkle" : ""),
        cx: (10 + rand() * (L.W - 20)).toFixed(1),
        cy: (10 + rand() * (L.H - 20)).toFixed(1),
        r: (big ? 0.9 + rand() * 0.7 : 0.3 + rand() * 0.6).toFixed(2),
        style: "--o:" + op.toFixed(2) + ";opacity:" + op.toFixed(2) + ";animation-delay:-" + (rand() * 6).toFixed(2) + "s",
      }));
    }
    L.regions.forEach(function (r, ri) {
      var nr = seeded(ri * 31 + 5);
      sky.append(sv("ellipse", { class: "bk-nebula", cx: r.cx.toFixed(1), cy: (r.cy + 6).toFixed(1), rx: (r.rx * 1.02).toFixed(1), ry: (r.ry * 0.95).toFixed(1), opacity: 0.2, filter: "url(#bk-nebula-blur)" }));
      r.members.forEach(function (c) {
        sky.append(sv("ellipse", {
          class: "bk-nebula",
          cx: (c.x + (nr() - 0.5) * 50).toFixed(1),
          cy: (c.y + (nr() - 0.5) * 30).toFixed(1),
          rx: (38 + nr() * 30).toFixed(1),
          ry: (26 + nr() * 22).toFixed(1),
          opacity: (0.1 + nr() * 0.08).toFixed(2),
          filter: "url(#bk-nebula-blur)",
        }));
      });
    });
    svg.append(sky);
    svg.append(sv("rect", { class: "bk-map-frame", x: 10, y: 10, width: L.W - 20, height: L.H - 20, rx: 12 }));
    var roads = sv("g");
    roadPaths(L, roads);
    svg.append(roads);
    L.regions.forEach(function (r) { svg.append(regionLabel(r, 10)); });
    L.cities.forEach(function (c) {
      var g = cityGroup(c);
      var x = c.x.toFixed(1), y = c.y.toFixed(1);
      g.append(sv("circle", { class: "bk-star-glow", cx: x, cy: y, r: (c.r * 1.25).toFixed(1), filter: "url(#bk-star-glow)" }));
      if (c.t.books.length >= 3) {
        var s = c.r * 1.9;
        g.append(sv("path", { class: "bk-star-spike", d: "M" + (c.x - s).toFixed(1) + " " + y + "H" + (c.x + s).toFixed(1) + "M" + x + " " + (c.y - s).toFixed(1) + "V" + (c.y + s).toFixed(1) }));
      }
      g.append(sv("circle", { class: "bk-star-core", cx: x, cy: y, r: (c.r * 0.42 + 1.1).toFixed(1) }));
      g.append(cityLabel(c));
      svg.append(g);
    });
    svg.append(legend(L, L.W - 200));
  }

  function buildMap() {
    var L = layoutMap();
    if (!L) return null;
    var wrap = el("div", "bk-map-scroll");
    var svg = sv("svg", {
      class: "bk-map is-" + THEME,
      viewBox: "0 0 " + L.W + " " + L.H,
      role: "group",
      "aria-label": "知识地图：" + L.regions.map(function (r) { return r.d.name + " " + r.members.length + " 个主题"; }).join("，"),
    });
    svg.style.setProperty("--map-mw", Math.round(L.W * 0.78) + "px");
    (THEME === "stars" ? drawStars : THEME === "kami" ? drawKami : drawYutu)(svg, L);
    wrap.append(svg);

    // Hovering or focusing a city lights up its roads and the cities they reach.
    var roadEls = Array.from(svg.querySelectorAll(".bk-road[data-a]"));
    var cityEls = Array.from(svg.querySelectorAll(".bk-city"));
    var hovered = null, focused = null;
    var light = function (i) {
      svg.classList.toggle("is-focus", i !== null);
      var linked = {};
      if (i !== null) linked[i] = true;
      roadEls.forEach(function (r) {
        var on = i !== null && (r.getAttribute("data-a") === i || r.getAttribute("data-b") === i);
        r.classList.toggle("is-on", on);
        if (on) linked[r.getAttribute("data-a") === i ? r.getAttribute("data-b") : r.getAttribute("data-a")] = true;
      });
      cityEls.forEach(function (c) { c.classList.toggle("is-on", !!linked[c.getAttribute("data-topic")]); });
    };
    var sync = function () { light(hovered !== null ? hovered : focused); };
    cityEls.forEach(function (c) {
      var id = c.getAttribute("data-topic");
      c.addEventListener("pointerenter", function () { hovered = id; sync(); });
      c.addEventListener("pointerleave", function () { hovered = null; sync(); });
      c.addEventListener("focus", function () { focused = id; sync(); });
      c.addEventListener("blur", function () { focused = null; sync(); });
      c.addEventListener("click", function () { openTopic(Number(id)); });
      c.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openTopic(Number(id));
        }
      });
    });
    return wrap;
  }

  if (topics.length) {
    var atlas = el("section", "bk-atlas");
    atlas.setAttribute("aria-label", "知识地图");
    var map = buildMap();
    if (map) atlas.append(map);
    var tl = el("ol", "bk-topics");
    topics.forEach(function (t, i) {
      var li = el("li");
      var btn = el("button", "bk-topic");
      btn.type = "button";
      btn.setAttribute("aria-haspopup", "dialog");
      btn.append(el("span", "bk-topic-domain", t.domain), el("span", "bk-topic-name", t.name));
      if (t.oneLiner) btn.append(el("span", "bk-topic-line", t.oneLiner));
      var meta = el("span", "bk-book-meta");
      meta.append(el("span", null, t.books.length + " 本书"), el("span", null, "≥ " + fmtNum(t.hours) + " h"));
      btn.append(meta);
      btn.addEventListener("click", function () { openTopic(i); });
      li.append(btn);
      tl.append(li);
    });
    atlas.append(tl);
    app.append(atlas);
  }

  // --------------------------------------------------------------- shelf

  function cover(b, size) {
    var ph = function () {
      var p = el("span", "bk-cover-ph" + (size ? " is-" + size : ""), b.title);
      p.setAttribute("aria-hidden", "true");
      return p;
    };
    if (!b.cover) return ph();
    var img = el("img");
    img.src = b.cover;
    img.alt = size ? "" : "《" + b.title + "》封面";
    img.loading = "lazy";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    img.width = size === "mini" ? 52 : size === "large" ? 84 : 120;
    img.height = size === "mini" ? 74 : size === "large" ? 120 : 172;
    img.addEventListener("error", function () { img.replaceWith(ph()); }, { once: true });
    return img;
  }

  if (books.length) {
    var picks = el("section", "bk-picks");
    picks.setAttribute("aria-label", "书架");
    var tools = el("div", "bk-tools");
    var sort = el("div", "bk-sort");
    sort.setAttribute("role", "group");
    sort.setAttribute("aria-label", "排序方式");
    var sortBtns = [["hours", "阅读时长"], ["recent", "最近阅读"]].map(function (s, k) {
      var b = el("button", "bk-sort-btn" + (k ? "" : " is-active"), s[1]);
      b.type = "button";
      b.setAttribute("data-sort", s[0]);
      b.setAttribute("aria-pressed", String(!k));
      sort.append(b);
      return b;
    });
    tools.append(sort);
    var filter = el("div", "bk-filter");
    filter.setAttribute("role", "group");
    filter.setAttribute("aria-label", "按领域筛选");
    var chipDefs = [{ name: null, label: "全部", n: books.length }].concat(
      D.domains.filter(function (d) { return d.books > 0; }).map(function (d) { return { name: d.name, label: d.name, n: d.books }; })
    );
    var chips = chipDefs.map(function (c, k) {
      var b = el("button", "bk-chip-btn" + (k ? "" : " is-active"), c.label);
      b.type = "button";
      b.setAttribute("aria-pressed", String(!k));
      b.append(el("span", null, String(c.n)));
      filter.append(b);
      return b;
    });
    var grid = el("ol", "bk-grid");
    var items = books.map(function (b, i) {
      var li = el("li");
      li.setAttribute("data-idx", i);
      var btn = el("button", "bk-book");
      btn.type = "button";
      btn.setAttribute("aria-haspopup", "dialog");
      var shelf = el("span", "bk-shelf");
      shelf.append(cover(b));
      var body = el("span", "bk-book-body");
      body.append(el("span", "bk-book-title", b.title));
      if (b.author) body.append(el("span", "bk-book-author", b.author));
      if (b.card) body.append(el("span", "bk-book-verdict" + (b.cardIsQuote ? " is-quote" : ""), b.card));
      var meta = el("span", "bk-book-meta");
      meta.append(el("span", null, b.finished ? b.finished.slice(0, 7).replace("-", ".") + " 读完" : "读到 " + b.progress + "%"));
      if (b.hours > 0) meta.append(el("span", null, "≥ " + fmtNum(b.hours) + " h"));
      if (b.domains[0]) meta.append(el("span", null, b.domains[0]));
      body.append(meta);
      btn.append(shelf, body);
      btn.addEventListener("click", function () { openBook(i); });
      li.append(btn);
      grid.append(li);
      return li;
    });
    sortBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-sort");
        sortBtns.forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
          b.setAttribute("aria-pressed", String(b === btn));
        });
        var sorted = items.slice().sort(function (a, b) {
          var ia = Number(a.getAttribute("data-idx")), ib = Number(b.getAttribute("data-idx"));
          if (mode === "recent") {
            var c = (books[ib].readAt || "").localeCompare(books[ia].readAt || "");
            if (c) return c;
          }
          return ia - ib;
        });
        sorted.forEach(function (li) { grid.append(li); });
      });
    });
    chips.forEach(function (chip, k) {
      chip.addEventListener("click", function () {
        var name = chipDefs[k].name;
        chips.forEach(function (c) {
          c.classList.toggle("is-active", c === chip);
          c.setAttribute("aria-pressed", String(c === chip));
        });
        items.forEach(function (li) {
          var b = books[Number(li.getAttribute("data-idx"))];
          li.hidden = name !== null && b.domains.indexOf(name) < 0;
        });
      });
    });
    picks.append(tools, filter, grid);
    app.append(picks);
  }

  if (D.generatedAt) {
    app.append(el("footer", "bk-footnote", "数据于 " + D.generatedAt + " 从微信读书拉取。单本书的阅读时长只能算下限。想法保留原话。"));
  }

  // -------------------------------------------------------------- dialog

  var dlg = document.getElementById("bk-dialog");
  var body = document.getElementById("bk-dialog-body");
  var opener = null;

  function jump(label, kind, idx, cls) {
    var btn = el("button", cls || "bk-jump", label);
    btn.type = "button";
    btn.addEventListener("click", function () { kind === "book" ? openBook(idx) : openTopic(idx); });
    return btn;
  }
  function source(title, idx) {
    var cap = el("span", "bk-src");
    cap.append(idx === null || idx === undefined ? el("span", "bk-src-plain", "《" + title + "》") : jump("《" + books[idx].title + "》", "book", idx));
    return cap;
  }
  function show() {
    if (!dlg.open) {
      opener = document.activeElement;
      dlg.showModal();
    }
    dlg.scrollTop = 0;
    // Content was just replaced, so put focus on the new heading instead of losing it.
    var title = document.getElementById("bk-dialog-title");
    if (title) {
      title.tabIndex = -1;
      title.focus({ preventScroll: true });
    }
  }
  function note(quote, text, src) {
    var fig = el("figure", "bk-note");
    if (quote) fig.append(el("blockquote", null, quote));
    var cap = el("figcaption");
    cap.append(el("span", null, "我"), document.createTextNode(text));
    if (src) cap.append(src);
    fig.append(cap);
    return fig;
  }

  function openTopic(i) {
    var t = topics[i];
    if (!t) return;
    body.replaceChildren();
    var head = el("div", "bk-topic-head");
    head.append(el("p", "bk-dialog-score", t.domain + " · " + t.books.length + " 本书 · 至少 " + fmtNum(t.hours) + " 小时"));
    var h3 = el("h3", null, t.name);
    h3.id = "bk-dialog-title";
    head.append(h3);
    body.append(head);
    if (t.oneLiner) body.append(el("p", "bk-dialog-verdict", t.oneLiner));
    if (t.viewpoints.length) {
      var ol = el("ol", "bk-views");
      t.viewpoints.forEach(function (v) {
        var li = el("li");
        li.append(el("strong", null, v.claim));
        if (v.text) li.append(el("p", null, v.text));
        if (v.books.length) {
          var from = el("span", "bk-src");
          v.books.forEach(function (b) {
            from.append(b.idx === null ? el("span", "bk-src-plain", "《" + b.title + "》") : jump("《" + books[b.idx].title + "》", "book", b.idx));
          });
          li.append(from);
        }
        ol.append(li);
      });
      body.append(ol);
    }
    if (t.thoughts.length) {
      var notes = el("div", "bk-notes");
      t.thoughts.forEach(function (x) { notes.append(note(x.quote, x.text, x.title ? source(x.title, x.idx) : null)); });
      body.append(notes);
    }
    if (t.highlights.length) {
      var marks = el("ol", "bk-marks");
      t.highlights.forEach(function (x) {
        var li = el("li", null, x.text);
        if (x.title) li.append(source(x.title, x.idx));
        marks.append(li);
      });
      body.append(marks);
    }
    if (t.books.length) {
      var shelf = el("div", "bk-topic-books");
      t.books.forEach(function (bi) {
        var b = books[bi];
        var btn = jump("", "book", bi, "bk-mini");
        btn.setAttribute("aria-label", "《" + b.title + "》");
        btn.setAttribute("data-tip", "《" + b.title + "》");
        btn.append(cover(b, "mini"));
        shelf.append(btn);
      });
      body.append(shelf);
    }
    show();
  }

  function openBook(i) {
    var b = books[i];
    if (!b) return;
    body.replaceChildren();
    var head = el("div", "bk-dialog-head");
    var info = el("div");
    info.append(el("p", "bk-dialog-score", b.domains.join(" · ")));
    var h3 = el("h3", null, "《" + b.title + "》");
    h3.id = "bk-dialog-title";
    info.append(h3);
    if (b.author) info.append(el("p", "bk-book-author", b.author));
    var pills = el("ul", "bk-pills");
    [
      b.finished ? "读完于 " + b.finished : "读到 " + b.progress + "%",
      b.hours > 0 ? "至少读了 " + fmtNum(b.hours) + " 小时" : "",
      b.marks ? "划线 " + b.marks : "",
      b.thoughtCount ? "想法 " + b.thoughtCount : "",
    ].filter(Boolean).forEach(function (p) { pills.append(el("li", null, p)); });
    info.append(pills);
    head.append(cover(b, "large"), info);
    body.append(head);
    if (b.topics.length) {
      var row = el("div", "bk-topic-row");
      row.append(el("span", null, "归入的主题"));
      b.topics.forEach(function (ti) { row.append(jump(topics[ti].name, "topic", ti, "bk-jump is-topic")); });
      body.append(row);
    }
    if (b.thoughts.length) {
      var notes = el("div", "bk-notes");
      b.thoughts.forEach(function (t) { notes.append(note(t.quote, t.text)); });
      body.append(notes);
    }
    if (b.highlights.length) {
      var ol = el("ol", "bk-marks");
      b.highlights.forEach(function (m) { ol.append(el("li", null, m)); });
      body.append(ol);
    }
    if (b.category || b.link) {
      var foot = el("div", "bk-dialog-foot");
      var chipsBox = el("div", "bk-chips");
      if (b.category) chipsBox.append(el("span", "bk-chip", b.category));
      foot.append(chipsBox);
      if (b.link) {
        var a = el("a", "bk-link", "在微信读书打开 →");
        a.href = b.link;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        foot.append(a);
      }
      body.append(foot);
    }
    show();
  }

  dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });
  dlg.querySelector("[data-close]").addEventListener("click", function () { dlg.close(); });
  dlg.addEventListener("close", function () {
    hideTip();
    if (opener && document.contains(opener) && opener.focus) opener.focus({ preventScroll: true });
    opener = null;
  });

  // ------------------------------------------------------------- tooltip

  var tip = document.getElementById("bk-tip");
  function showTip(node, x, y) {
    tip.textContent = node.getAttribute("data-tip") || "";
    tip.hidden = false;
    var r = tip.getBoundingClientRect();
    tip.style.left = Math.min(Math.max(x - r.width / 2, 8), window.innerWidth - r.width - 8) + "px";
    tip.style.top = Math.max(y - r.height - 12, 8) + "px";
  }
  function hideTip() {
    tip.hidden = true;
  }
  document.addEventListener("pointermove", function (e) {
    var node = e.target && e.target.closest ? e.target.closest("[data-tip]") : null;
    if (node) showTip(node, e.clientX, e.clientY);
    else if (!tip.hidden) hideTip();
  });
  document.addEventListener("pointerleave", hideTip);
  function tipAtFocus() {
    var node = document.activeElement && document.activeElement.closest ? document.activeElement.closest("[data-tip]") : null;
    if (!node || dlg.open) return hideTip();
    var r = node.getBoundingClientRect();
    showTip(node, r.left + r.width / 2, r.top);
  }
  document.addEventListener("focusin", tipAtFocus);
  document.addEventListener("focusout", hideTip);
  // Keyboard focus that scrolls the page keeps its tip; a pointer tip just goes away.
  window.addEventListener("scroll", tipAtFocus, { passive: true });

  // ----------------------------------------------------------- night sky

  if (THEME === "stars") {
    var sky = sv("svg", { class: "bk-sky", viewBox: "0 0 1600 1000", preserveAspectRatio: "xMidYMid slice", "aria-hidden": "true" });
    var rnd = seeded(20221);
    for (var s = 0; s < 240; s++) {
      var bright = rnd() > 0.94;
      var o = bright ? 0.6 + rnd() * 0.3 : 0.12 + rnd() * 0.35;
      sky.append(sv("circle", {
        class: bright ? "is-twinkle" : null,
        cx: (rnd() * 1600).toFixed(1),
        cy: (rnd() * 1000).toFixed(1),
        r: (bright ? 1 + rnd() * 0.8 : 0.35 + rnd() * 0.6).toFixed(2),
        style: "--o:" + o.toFixed(2) + ";opacity:" + o.toFixed(2) + ";animation-delay:-" + (rnd() * 6).toFixed(2) + "s",
      }));
    }
    document.body.prepend(sky);
  }
})();
