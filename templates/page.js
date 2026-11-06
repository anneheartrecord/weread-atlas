// 书脉 · 书房页. Everything below is built from the JSON in #bk-data, so the
// page is one file with no build step. Text always goes in through
// textContent, never innerHTML. The ring's geometry comes precomputed from
// render.py; this file only draws it and wires up the interactions.
(function () {
  "use strict";

  var D = JSON.parse(document.getElementById("bk-data").textContent);
  var SVGNS = "http://www.w3.org/2000/svg";
  var app = document.getElementById("bk-app");
  var books = D.books || [];
  var topics = D.topics || [];
  var relations = D.relations || [];
  var stats = D.stats;

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
  function fmtHours(h) {
    return h >= 10 ? String(Math.round(h)) : (Math.round(h * 10) / 10).toFixed(1);
  }
  function fmtNum(v) {
    return String(Math.round(v * 10) / 10);
  }
  function monthLabel(m) {
    return m.slice(0, 4) + " 年 " + Number(m.slice(5, 7)) + " 月";
  }
  function maxOf(arr, key) {
    return arr.reduce(function (a, x) { return Math.max(a, x[key]); }, 0) || 1;
  }

  // --------------------------------------------------------------- hero

  (function () {
    var items = [];
    if (stats) {
      items.push({ value: String(Math.round(stats.totalHours)), unit: "小时", label: "累计阅读" });
      if (stats.readDays) items.push({ value: String(stats.readDays), unit: "天", label: "有阅读的日子" });
      items.push({ value: String(stats.readBooks), unit: "本", label: "读过" });
      items.push({ value: String(stats.finishedBooks), unit: "本", label: "读完" });
      items.push({ value: String(stats.notes), unit: "条", label: "划线和想法" });
    } else {
      var hours = books.reduce(function (a, b) { return a + b.hours; }, 0);
      var notes = books.reduce(function (a, b) { return a + b.marks + b.thoughtCount; }, 0);
      items.push({ value: fmtHours(hours), unit: "小时", label: "累计阅读" });
      items.push({ value: String(books.length), unit: "本", label: "有笔记的书" });
      items.push({ value: String(books.filter(function (b) { return b.finished; }).length), unit: "本", label: "读完" });
      items.push({ value: String(notes), unit: "条", label: "划线和想法" });
    }
    var hero = el("header", "bk-hero");
    hero.append(el("h1", null, D.title || "书脉"));
    var ledger = el("dl", "bk-ledger");
    ledger.setAttribute("aria-label", "阅读总览");
    items.forEach(function (s) {
      var box = el("div", "bk-stat");
      var v = el("dd", "bk-stat-value", s.value);
      v.append(el("span", null, s.unit));
      box.append(el("dt", "bk-stat-label", s.label), v);
      ledger.append(box);
    });
    hero.append(ledger);
    app.append(hero);
  })();

  // ---------------------------------------------------- knowledge ring

  // Small inline button that swaps the dialog to another book or topic.
  function jump(label, kind, idx, cls) {
    var btn = el("button", cls || "bk-jump", label);
    btn.type = "button";
    btn.addEventListener("click", function () { kind === "book" ? openBook(idx) : openTopic(idx); });
    return btn;
  }

  var R = D.ring;
  if (topics.length && R) {
    var atlas = el("section", "bk-atlas");
    atlas.setAttribute("aria-label", "知识脉络");
    var scroll = el("div", "bk-map-scroll");
    var mapDomains = R.arcs.map(function (g) {
      return g.name + " " + topics.filter(function (t) { return t.domain === g.name; }).length + " 个主题";
    });
    var map = sv("svg", { class: "bk-map", viewBox: "0 0 " + R.size + " " + R.size, role: "group", "aria-label": "知识脉络：" + mapDomains.join("，") });
    R.arcs.forEach(function (g) {
      var dg = sv("g", { class: "bk-domain" });
      dg.append(sv("path", { class: "bk-domain-arc", d: g.d }));
      dg.append(sv("text", { class: "bk-domain-label", x: g.x, y: g.y, "text-anchor": "middle", "dominant-baseline": "middle", style: "font-size:" + R.domainPx + "px" }, g.name));
      map.append(dg);
    });
    var roads = relations.map(function (rel, k) {
      var road = R.roads[k];
      var p = sv("path", {
        class: "bk-road" + (rel.cross ? " is-sea" : "") + (rel.kind === "books" ? " is-books" : ""),
        d: road.d,
        "data-a": rel.a,
        "data-b": rel.b,
        style: "stroke-width:" + road.w,
      });
      map.append(p);
      return p;
    });
    var hit = Math.max(10, R.labelPx + 1);
    var nodes = topics.map(function (t, i) {
      var n = R.nodes[i];
      var g = sv("g", {
        class: "bk-city",
        "data-node": i,
        tabindex: "0",
        role: "button",
        "aria-label": t.name + "，" + t.books.length + " 本书，至少 " + fmtNum(t.hours) + " 小时",
        "data-tip": t.name + "｜" + t.books.length + " 本书｜≥ " + fmtNum(t.hours) + " 小时",
      });
      g.append(sv("circle", { class: "bk-node-hit", cx: n.x, cy: n.y, r: hit }));
      g.append(sv("circle", { class: "bk-node", cx: n.x, cy: n.y, r: n.dot }));
      g.append(sv("text", {
        class: "bk-node-label",
        x: n.lx,
        y: n.ly,
        "text-anchor": n.anchor,
        "dominant-baseline": "middle",
        transform: "rotate(" + n.rot + " " + n.lx + " " + n.ly + ")",
        style: "font-size:" + R.labelPx + "px",
      }, n.label));
      map.append(g);
      return g;
    });
    scroll.append(map);

    // The side panel: by default the veins that cross domains, each with its reason.
    var veins = el("aside", "bk-veins");
    veins.setAttribute("aria-live", "polite");
    var head = el("div", "bk-veins-head");
    var list = el("ol", "bk-veins-list");
    veins.append(head, list);
    atlas.append(scroll, veins);
    app.append(atlas);

    var crossRels = relations.filter(function (r) { return r.cross; });
    var pinned = null;

    var light = function (pick, center) {
      var lit = {};
      center.forEach(function (c) { lit[c] = true; });
      roads.forEach(function (p, k) {
        var on = pick(relations[k]);
        p.classList.toggle("is-on", on);
        if (on) {
          lit[relations[k].a] = true;
          lit[relations[k].b] = true;
        }
      });
      nodes.forEach(function (n, i) { n.classList.toggle("is-on", !!lit[i]); });
      map.classList.add("is-focus");
    };
    var clear = function () {
      map.classList.remove("is-focus");
      roads.forEach(function (p) { p.classList.remove("is-on"); });
      nodes.forEach(function (n) { n.classList.remove("is-on", "is-pinned"); });
    };
    var showTopic = function (i) {
      light(function (r) { return r.a === i || r.b === i; }, [i]);
    };
    var showPair = function (a, b) {
      light(function (r) { return (r.a === a && r.b === b) || (r.a === b && r.b === a); }, [a, b]);
    };
    var restore = function () {
      if (pinned === null) clear();
      else showTopic(pinned);
    };
    var veinButton = function (a, b, pairEl, why, extra) {
      var li = el("li");
      var btn = el("button", "bk-vein");
      btn.type = "button";
      btn.append(pairEl);
      if (why) btn.append(el("span", "bk-vein-why", why));
      if (extra) btn.append(el("span", "bk-vein-books", extra));
      btn.addEventListener("pointerenter", function () { showPair(a, b); });
      btn.addEventListener("focus", function () { showPair(a, b); });
      btn.addEventListener("pointerleave", restore);
      btn.addEventListener("blur", restore);
      // In a pinned topic's list, a row moves the pin to the other topic; in the overview it pins the first one.
      btn.addEventListener("click", function () { pin(pinned === a ? b : a); });
      li.append(btn);
      return li;
    };
    var overview = function () {
      head.replaceChildren();
      list.replaceChildren();
      var shown = crossRels.length ? crossRels : relations;
      head.append(el("p", "bk-veins-kicker", crossRels.length ? "跨领域的脉络" : "主题之间的脉络"));
      if (!shown.length) {
        list.append(el("li", "bk-vein-empty", "主题之间还没有记录到联系。点一个主题，看它的书和观点。"));
        return;
      }
      shown.forEach(function (r) {
        var pair = el("span", "bk-vein-pair", topics[r.a].name);
        pair.append(el("i", null, "·"), document.createTextNode(topics[r.b].name));
        list.append(veinButton(r.a, r.b, pair, r.why));
      });
    };
    var panelFor = function (i) {
      var t = topics[i];
      head.replaceChildren();
      head.append(el("p", "bk-veins-kicker", t.domain + " · " + t.books.length + " 本书 · 至少 " + fmtNum(t.hours) + " 小时"));
      head.append(el("h3", "bk-veins-title", t.name));
      var actions = el("div", "bk-veins-actions");
      var back = el("button", "bk-veins-back", "看全部脉络");
      back.type = "button";
      back.addEventListener("click", unpin);
      actions.append(jump("展开这个主题", "topic", i, "bk-veins-open"), back);
      head.append(actions);
      list.replaceChildren();
      var mine = relations
        .filter(function (r) { return r.a === i || r.b === i; })
        .sort(function (x, y) {
          return Number(y.cross) - Number(x.cross) || Number(y.kind === "concept") - Number(x.kind === "concept");
        });
      if (!mine.length) list.append(el("li", "bk-vein-empty", "这个主题和其他主题之间还没有记录到联系。"));
      mine.forEach(function (r) {
        var other = r.a === i ? r.b : r.a;
        var pair = el("span", "bk-vein-pair", topics[other].name);
        if (r.cross) pair.append(el("em", null, topics[other].domain));
        list.append(veinButton(i, other, pair, r.why, r.kind === "concept" && r.sharedBooks ? "共读 " + r.sharedBooks : ""));
      });
    };
    var pin = function (i) {
      pinned = i;
      showTopic(i);
      nodes.forEach(function (n, k) { n.classList.toggle("is-pinned", k === i); });
      panelFor(i);
    };
    var unpin = function () {
      pinned = null;
      clear();
      overview();
    };
    overview();
    nodes.forEach(function (n, i) {
      n.addEventListener("pointerenter", function () { showTopic(i); });
      n.addEventListener("pointerleave", restore);
      n.addEventListener("focus", function () { showTopic(i); });
      n.addEventListener("blur", restore);
      // First click pins the topic; clicking the pinned topic again opens it.
      n.addEventListener("click", function () { pinned === i ? openTopic(i) : pin(i); });
      n.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          pinned === i ? openTopic(i) : pin(i);
        }
      });
    });
  }

  // ------------------------------------------------------ reading rhythm

  function bar(cls, heightPct, tip, label) {
    var b = el("div", "bk-bar" + (cls ? " " + cls : ""));
    b.style.height = heightPct + "%";
    b.tabIndex = 0;
    b.setAttribute("data-tip", tip);
    b.setAttribute("aria-label", label);
    return b;
  }

  if (stats && (stats.months.length || stats.years.length || stats.hourly.length)) {
    var rhythm = el("section", "bk-rhythm");
    rhythm.setAttribute("aria-label", "阅读节奏");

    if (stats.months.length) {
      var first = stats.months.findIndex(function (m) { return m.hours > 0; });
      var months = stats.months.slice(Math.max(first, 0));
      var maxMonth = maxOf(months, "hours");
      var peakMonth = months.reduce(function (a, b) { return b.hours > a.hours ? b : a; });
      var main = el("div", "bk-rhythm-main");
      var mc = el("div", "bk-month-chart");
      mc.setAttribute("role", "group");
      mc.setAttribute("aria-label", "每月阅读时长");
      var ma = el("div", "bk-month-axis");
      ma.setAttribute("aria-hidden", "true");
      months.forEach(function (m, k) {
        var col = el("div", "bk-month-col");
        col.append(bar(m.month === peakMonth.month ? "is-peak" : "", Math.max((m.hours / maxMonth) * 100, m.hours > 0 ? 2 : 0.6),
          monthLabel(m.month) + "｜" + fmtNum(m.hours) + " 小时", monthLabel(m.month) + " " + fmtNum(m.hours) + " 小时"));
        mc.append(col);
        // Each January carries its year; the first month does too unless a January follows right after.
        var jan = m.month.slice(5) === "01";
        var lead = k === 0 && !months.slice(1, 4).some(function (x) { return x.month.slice(5) === "01"; });
        ma.append(el("span", null, jan || lead ? m.month.slice(0, 4) : ""));
      });
      main.append(mc, ma);
      rhythm.append(main);
    }

    var row = el("div", "bk-rhythm-row");
    if (stats.years.length) {
      var curYear = Number((stats.generatedAt || "").slice(0, 4));
      var asOf = stats.generatedAt ? Number(stats.generatedAt.slice(5, 7)) + " 月 " + Number(stats.generatedAt.slice(8, 10)) + " 日" : "";
      var maxYear = maxOf(stats.years, "hours");
      var yWrap = el("div", "bk-rhythm-year");
      var yc = el("div", "bk-year-chart");
      yc.setAttribute("role", "group");
      yc.setAttribute("aria-label", "每年阅读时长");
      yc.style.gridTemplateColumns = "repeat(" + Math.max(stats.years.length, 3) + ", minmax(0, 1fr))";
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
      yWrap.append(yc);
      row.append(yWrap);
    }
    if (stats.hourly.length === 24) {
      var maxHour = maxOf(stats.hourly, "hours");
      var peakHour = stats.hourly.reduce(function (a, b) { return b.hours > a.hours ? b : a; });
      var hWrap = el("div", "bk-rhythm-hour");
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
      hWrap.append(hc, ha);
      row.append(hWrap);
    }
    // Reading-preference radar: the six categories with the most reading time, scaled to the largest.
    if (stats.categories.length >= 3) {
      var radarCats = stats.categories.slice(0, 6);
      var radarMax = maxOf(radarCats, "hours");
      var RD = { cx: 185, cy: 136, r: 84 };
      var pt = function (i, frac) {
        var a = -Math.PI / 2 + (i * 2 * Math.PI) / radarCats.length;
        return { x: RD.cx + frac * RD.r * Math.cos(a), y: RD.cy + frac * RD.r * Math.sin(a) };
      };
      var ringPts = function (frac) {
        return radarCats.map(function (_, i) { var p = pt(i, frac); return p.x.toFixed(1) + "," + p.y.toFixed(1); }).join(" ");
      };
      var radar = el("div", "bk-radar");
      var svg = sv("svg", {
        viewBox: "0 0 370 272",
        role: "img",
        "aria-label": "阅读偏好六维图：" + radarCats.map(function (c) { return c.name + " " + fmtNum(c.hours) + " 小时"; }).join("，"),
      });
      [0.25, 0.5, 0.75, 1].forEach(function (f) { svg.append(sv("polygon", { class: "bk-radar-ring", points: ringPts(f) })); });
      radarCats.forEach(function (_, i) {
        var p = pt(i, 1);
        svg.append(sv("line", { class: "bk-radar-axis", x1: RD.cx, y1: RD.cy, x2: p.x.toFixed(1), y2: p.y.toFixed(1) }));
      });
      var verts = radarCats.map(function (c, i) { return pt(i, Math.max(c.hours / radarMax, 0.06)); });
      svg.append(sv("polygon", { class: "bk-radar-shape", points: verts.map(function (v) { return v.x.toFixed(1) + "," + v.y.toFixed(1); }).join(" ") }));
      verts.forEach(function (v, i) {
        var c = radarCats[i];
        var g = sv("g", { class: "bk-radar-pt", tabindex: "0", "data-tip": c.name + "｜" + fmtNum(c.hours) + " 小时｜" + c.count + " 本" });
        g.append(sv("circle", { class: "bk-radar-hit", cx: v.x.toFixed(1), cy: v.y.toFixed(1), r: 13 }));
        g.append(sv("circle", { class: "bk-radar-dot", cx: v.x.toFixed(1), cy: v.y.toFixed(1), r: 4.5 }));
        svg.append(g);
      });
      radarCats.forEach(function (c, i) {
        var p = pt(i, 1.2);
        var anchor = Math.abs(p.x - RD.cx) < 4 ? "middle" : p.x > RD.cx ? "start" : "end";
        var t = sv("text", { class: "bk-radar-label", x: p.x.toFixed(1), y: p.y.toFixed(1), "text-anchor": anchor, "dominant-baseline": "middle" });
        t.append(sv("tspan", {}, c.name));
        t.append(sv("tspan", { class: "bk-radar-value", dx: 5 }, fmtNum(c.hours) + "h"));
        svg.append(t);
      });
      radar.append(svg);
      row.append(radar);
    }
    if (row.children.length) {
      if (row.children.length < 3) row.classList.add("is-" + row.children.length);
      rhythm.append(row);
    }
    app.append(rhythm);
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
    filter.setAttribute("role", "tablist");
    filter.setAttribute("aria-label", "按领域筛选");
    var chipDefs = [{ name: null, label: "全部", n: books.length }].concat(
      D.domains.filter(function (d) { return d.books > 0; }).map(function (d) { return { name: d.name, label: d.name, n: d.books }; })
    );
    var chips = chipDefs.map(function (c, k) {
      var b = el("button", "bk-chip-btn" + (k ? "" : " is-active"), c.label);
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(!k));
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
          c.setAttribute("aria-selected", String(c === chip));
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
    app.append(el("footer", "bk-footnote", "数据于 " + D.generatedAt + " 从微信读书拉取。单本书的阅读时长按每月阅读前 10 名累加，只能算下限。想法保留原话。"));
  }

  // -------------------------------------------------------------- dialog

  var dlg = document.getElementById("bk-dialog");
  var body = document.getElementById("bk-dialog-body");
  var opener = null;

  function source(title, idx) {
    var cap = el("span", "bk-src");
    cap.append(idx === null || idx === undefined ? el("span", "bk-src-plain", "《" + title + "》") : jump("《" + books[idx].title + "》", "book", idx));
    return cap;
  }
  function show() {
    hideTip();
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
    var mine = relations.filter(function (r) { return r.a === i || r.b === i; });
    if (mine.length) {
      var rel = el("div", "bk-related");
      rel.append(el("p", "bk-related-kicker", "相关主题"));
      var rl = el("ol");
      mine.forEach(function (r) {
        var other = r.a === i ? r.b : r.a;
        var li = el("li");
        li.append(jump(topics[other].name, "topic", other));
        if (r.cross) li.append(el("em", null, topics[other].domain));
        if (r.why) li.append(el("span", "bk-related-why", r.why));
        rl.append(li);
      });
      rel.append(rl);
      body.append(rel);
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
  document.addEventListener("focusin", function () {
    var node = document.activeElement && document.activeElement.closest ? document.activeElement.closest("[data-tip]") : null;
    if (!node || dlg.open) return hideTip();
    var r = node.getBoundingClientRect();
    showTip(node, r.left + r.width / 2, r.top);
  });
  document.addEventListener("focusout", hideTip);
  // A tooltip left over from a hover should not ride along when the page scrolls.
  window.addEventListener("scroll", hideTip, { passive: true });
})();
