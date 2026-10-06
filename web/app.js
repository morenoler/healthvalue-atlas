"use strict";
const $ = (id) => document.getElementById(id);
const state = {
  year: 2023,
  country: "POL",
  metric: "treatable",
  view: "overview",
  chart: "scatter"
};
const colors = {
  teal: "#7188ac",
  orange: "#285ed6",
  muted: "#a8b9d2",
  navy: "#252c37"
};
const metricMeaning = {
  treatable: "Смерти до 75 лет, предотвратимые своевременным лечением.",
  preventable: "Смерти до 75 лет, предотвратимые профилактикой.",
  avoidable: "Смерти до 75 лет, предотвратимые лечением или профилактикой."
};
const names = {
  treatable: "Смертность: своевременное лечение",
  preventable: "Смертность: профилактика",
  avoidable: "Вся предотвратимая смертность"
};
let atlas;
let world;
const fmt = (v, digits = 0) => v == null || !Number.isFinite(Number(v)) ? "Нет данных" : Number(v).toLocaleString("ru-RU", {
  maximumFractionDigits: digits,
  minimumFractionDigits: digits
});
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;"
} [c]));
const median = (a) => {
  const s = a.filter(Number.isFinite).sort((x, y) => x - y);
  return s.length ? (s[Math.floor((s.length - 1) / 2)] + s[Math.ceil((s.length - 1) / 2)]) / 2 : null;
};
const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
const svg = (w, h, body, label) => `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}">${body}</svg>`;
const current = () => atlas.panel.find(r => r.iso3 === state.country && r.year === state.year);
const yearRows = () => atlas.panel.filter(r => r.year === state.year);
const dotLabel = (r) => `${r.country}: расходы ${fmt(r.spend_ppp)} долларов по ППС, смертность ${fmt(r[state.metric],1)} на 100 000`;

function kpi(label, value, note, unit = "") {
  return `<article class="kpi"><p class="kpi-label">${label}</p><div class="kpi-value">${value} <small>${unit}</small></div><div class="kpi-note">${note}</div></article>`;
}

function chooseCountry(code) {
  state.country = code;
  $("country").value = code;
  $("tooltip").hidden = true;
  render();
}

function setView(view) {
  if (!["overview", "research", "forecast", "data"].includes(view)) view = "overview";
  state.view = view;
  const countryPanel = document.querySelector('.country-panel');
  if (countryPanel) {
    $('country-dock').append(countryPanel);
    countryPanel.hidden = view !== 'overview';
  }
  document.querySelectorAll(".view").forEach(el => {
    el.hidden = el.id !== view;
    el.classList.toggle("active", el.id === view);
  });
  document.querySelectorAll(".nav-item").forEach(el => {
    const active = el.dataset.view === view;
    el.classList.toggle("active", active);
    if (active) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  const titles = {
    overview: ["Здравоохранение в цифрах", "Расходы, смертность и различия между странами на открытых данных ОЭСР, ВОЗ и Всемирного банка."],
    research: ["Расходы и смертность", "Эффекты стран и лет, устойчивость оценки и сценарий изменения расходов."],
    forecast: ["Качество прогноза", "Сравнение моделей с простым прогнозом по прошлому году. Выбор модели по временной валидации."],
    data: ["Данные и методология", "Источники, пропуски и определения. Каждое число можно проверить и скачать."]
  };
  $("page-title").innerHTML = titles[view][0];
  $("metric").disabled = ["research", "forecast"].includes(view);
  $("year").disabled = view === "forecast";
  $("metric").closest("label").hidden = ["research", "forecast"].includes(view);
  $("year").closest("label").hidden = view === "forecast";
  if (location.hash !== `#${view}`) history.replaceState(null, "", `#${view}`);
  if (atlas) render();
}

function renderOverview() {
  const rows = yearRows().filter(r => r.spend_ppp != null && r[state.metric] != null);
  const r = current(),
    medRate = median(rows.map(r => r[state.metric])),
    medSpend = median(rows.map(r => r.spend_ppp));
  const gap = r?.[state.metric] != null && medRate ? (r[state.metric] / medRate - 1) * 100 : null;
  const comparison = gap == null
    ? "Нет данных для сравнения смертности с медианой"
    : Math.abs(gap) < 0.05
      ? "Смертность на уровне медианы выборки"
      : `Смертность на <strong>${fmt(Math.abs(gap), 1)}%</strong> ${gap > 0 ? "выше" : "ниже"} медианы выборки`;
  const comparisonHelp = gap == null
    ? "Для расчёта нужны смертность выбранной страны и ненулевая медиана. Нет данных — не означает ноль."
    : `${esc(r.country)}: ${fmt(r[state.metric], 1)} на 100 тыс.; медиана: ${fmt(medRate, 1)}. Разница: (${fmt(r[state.metric], 1)} / ${fmt(medRate, 1)} − 1) × 100 = ${gap > 0 ? "+" : ""}${fmt(gap, 1)}%. Это сравнение стран за один год, а не изменение со временем. Расчёт выполнен до округления.`;
  $("kpis").innerHTML = `
    <div class="summary-context"><span>Медианы выборки · ${state.year}</span><span>${rows.length} из ${atlas.quality.countries} стран</span></div>
    <div class="summary-values">
      <div class="summary-metric"><span class="summary-label">Расходы на человека</span><div class="summary-number">${fmt(medSpend)} <span>$ ППС</span></div><small class="metric-explanation">Расходы на здоровье с поправкой на разницу цен между странами.</small></div>
      <div class="summary-metric"><span class="summary-label">Смертность</span><div class="summary-number">${fmt(medRate, 1)} <span>на 100 тыс.</span></div><small class="metric-explanation">${metricMeaning[state.metric]}</small></div>
    </div>
    <details class="data-detail"><summary>Что значит медиана?</summary><p>Середина выборки: у половины стран показатель ниже, у половины — выше. Расходы даны в текущих ценах; смертность скорректирована по возрасту.</p><p>${rows.length} из ${atlas.quality.countries} стран — столько имеют одновременно данные о расходах и выбранной смертности за ${state.year} год. Остальные не входят в эти медианы.</p><p>Смертность — стандартизованный показатель для сравнения стран с разным возрастным составом, а не фактическое число умерших.</p></details>
    <div class="summary-comparison"><span class="summary-country">${esc(r.country)}</span><span>${comparison}</span><details class="data-detail"><summary>Как получено это число?</summary><p>${comparisonHelp}</p></details></div>`;
  $("scatter-year").textContent = state.year;
  $("map-label").hidden = state.chart !== "map";
  if (state.chart === "map") renderMap();
  else {
    $("scatter-caption").textContent = "Каждая точка — страна.";
    $("scatter-legend").innerHTML = '<span><b class="legend-dot teal"></b>Выборка</span><span><b class="legend-dot orange"></b>Выбранная страна</span><span>Текущие $ по ППС · логарифмическая шкала</span>';
    renderScatter(rows);
  }
  $("profile-name").textContent = r.country;
  $("profile-code").textContent = r.iso3;
  $("profile-stats").innerHTML = [
    ["Расходы на человека", r.spend_ppp, 0, " $ ППС", "В год, с поправкой на разницу цен"],
    ["Смертность на 100 000", r[state.metric], 1, "", "Выбранная категория, с учётом возраста"],
    ["Прямые платежи граждан", r.oop_share, 1, "%", r.oop_share == null ? "Доля расходов, оплаченная из своего кармана; данных нет" : `Из каждых 100 денежных единиц расходов на здоровье ${fmt(r.oop_share, 1)} оплачены напрямую гражданами`],
    ["Доля населения 65+", r.age65_pct, 1, "%", r.age65_pct == null ? "Жители в возрасте 65 лет и старше; данных нет" : `Примерно ${fmt(r.age65_pct, 1)} из 100 жителей — в возрасте 65 лет и старше`]
  ].map(([label, v, d, u, meaning]) => `<div class="stat-row"><span>${label}<small class="metric-explanation">${meaning}</small></span><b>${fmt(v,d)}${v==null?"":u}</b></div>`).join("");
  renderTrend();
  renderPeers();
  $("insight").textContent = `В срезе за 2023 год корреляция расходов и смертности из категории «лечение» равна ${fmt(atlas.findings.spearman_spend_mortality,2)}. Коэффициент от −1 до +1: минус означает, что большие расходы связаны с меньшей смертностью; близость к −1 — более сильную обратную связь. Это не доказательство причинности. Панельная модель проверяет, как вывод меняется после учёта дохода, демографии и постоянных различий.`;
}

function renderScatter(rows) {
  const w = 620,
    h = 350,
    m = {
      l: 58,
      r: 25,
      t: 24,
      b: 52
    };
  if (!rows.length) {
    $("scatter").innerHTML = '<p class="empty">Нет сопоставимых наблюдений.</p>';
    return;
  }
  const xMin = Math.floor(Math.log10(Math.min(...rows.map(r => r.spend_ppp))) * 2) / 2;
  const xMax = Math.ceil(Math.log10(Math.max(...rows.map(r => r.spend_ppp))) * 2) / 2;
  const ymax = Math.ceil(Math.max(...rows.map(r => r[state.metric])) / 50) * 50;
  const x = v => m.l + (Math.log10(v) - xMin) / (xMax - xMin) * (w - m.l - m.r),
    y = v => h - m.b - v / ymax * (h - m.t - m.b);
  let body = `<text x="${m.l}" y="12" class="svg-title">Смертность на 100 000 · меньше лучше</text>`;
  for (let i = 0; i <= 4; i++) {
    const v = ymax * i / 4;
    body += `<line x1="${m.l}" y1="${y(v)}" x2="${w-m.r}" y2="${y(v)}" class="svg-grid"/><text x="${m.l-10}" y="${y(v)+4}" text-anchor="end" class="svg-label">${fmt(v)}</text>`;
  }
  const ticks = [300, 500, 1000, 2000, 3000, 5000, 10000, 15000, 20000];
  for (const t of ticks.filter(v => Math.log10(v) >= xMin && Math.log10(v) <= xMax)) {
    body += `<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${h-m.b}" class="svg-grid"/><text x="${x(t)}" y="${h-m.b+22}" text-anchor="middle" class="svg-label">${t>=1000?`${t/1000}k`:t}</text>`;
  }
  body += `<text x="${w/2}" y="${h-5}" text-anchor="middle" class="svg-title">Расходы на человека, $ по ППС</text>`;
  const sorted = rows.slice().sort((a, b) => (a.iso3 === state.country) - (b.iso3 === state.country));
  for (const r of sorted) {
    const sel = r.iso3 === state.country;
    body += `<circle class="dot" cx="${x(r.spend_ppp)}" cy="${y(r[state.metric])}" r="${sel?8:5.5}" fill="${sel?colors.orange:colors.teal}" opacity="${sel?1:.6}" stroke="white" stroke-width="1.5" tabindex="0" role="button" data-country="${r.iso3}" aria-label="${esc(dotLabel(r))}"><title>${esc(dotLabel(r))}</title></circle>`;
    if (sel) body += `<text x="${x(r.spend_ppp)+12}" y="${y(r[state.metric])-8}" class="svg-label" style="fill:${colors.orange};font-weight:700">${r.iso3}</text>`;
  }
  $("scatter").innerHTML = svg(w, h, body, `Расходы и ${names[state.metric]}, ${state.year}`);
  $("scatter").querySelectorAll(".dot").forEach(el => {
    const row = rows.find(r => r.iso3 === el.dataset.country);
    const show = (e) => {
      const b = el.getBoundingClientRect();
      const px = e.clientX || b.x,
        py = e.clientY || b.y;
      const tip = $("tooltip");
      tip.innerHTML = `<b>${esc(row.country)}</b>${fmt(row.spend_ppp)} $ ППС / человек<br>${fmt(row[state.metric],1)} на 100 000<br><small>${state.year} · ${row.iso3}</small>`;
      tip.style.left = `${Math.min(px+15,innerWidth-245)}px`;
      tip.style.top = `${Math.min(py+15,innerHeight-120)}px`;
      tip.hidden = false;
    };
    el.addEventListener("pointermove", show);
    el.addEventListener("focus", show);
    el.addEventListener("pointerleave", () => $("tooltip").hidden = true);
    el.addEventListener("blur", () => $("tooltip").hidden = true);
    el.addEventListener("click", () => chooseCountry(el.dataset.country));
    el.addEventListener("keydown", e => {
      if (["Enter", " "].includes(e.key)) {
        e.preventDefault();
        chooseCountry(el.dataset.country);
      }
    });
  });
}

function renderMap() {
  const column = $("map-variable").value === "spend_ppp" ? "spend_ppp" : state.metric;
  const rows = yearRows(),
    values = rows.map(r => r[column]).filter(Number.isFinite);
  const low = Math.min(...values),
    high = Math.max(...values);
  const unit = column === "spend_ppp" ? "$ ППС / человек" : "на 100 000";
  const color = v => {
    if (v == null) return "#d9dfe8";
    const t = (v - low) / (high - low || 1);
    return `rgb(${Math.round(196-156*t)},${Math.round(214-128*t)},${Math.round(240-80*t)})`;
  };
  const project = ([lon, lat]) => `${(15+(lon+180)/360*590).toFixed(2)},${(27+(85-lat)/145*265).toFixed(2)}`;
  let body = '<rect x="0" y="0" width="620" height="330" fill="#edf1f7" rx="8"/>';
  const sorted = world.slice().sort((a, b) => (a.iso3 === state.country) - (b.iso3 === state.country));
  for (const feature of sorted) {
    const row = rows.find(r => r.iso3 === feature.iso3),
      selected = feature.iso3 === state.country;
    const polygons = feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
    const path = polygons.map(p => p.map(ring => `M${ring.map(project).join("L")}Z`).join("")).join("");
    const title = row ? `${row.country}: ${fmt(row[column],1)} ${unit}` : `${feature.name}: вне выборки`;
    body += `<path d="${path}" fill="${color(row?.[column])}" fill-rule="evenodd" stroke="${selected?colors.navy:"#fff"}" stroke-width="${selected?.8:.15}" ${row?`class="map-country" role="button" tabindex="0" data-country="${row.iso3}" aria-label="${esc(title)}"`:""}><title>${esc(title)}</title></path>`;
  }
  body += '<text x="15" y="319" class="svg-small">Границы: Natural Earth · страны вне выборки показаны серым</text>';
  $("scatter").innerHTML = svg(620, 330, body, `Карта: ${column==="spend_ppp"?"расходы":names[state.metric]}, ${state.year}`);
  $("scatter-caption").textContent = `Цвет: ${column==="spend_ppp"?"расходы на человека":names[state.metric].toLowerCase()}. Шкала рассчитана для выбранного года.`;
  $("scatter-legend").innerHTML = `<span>${fmt(low)} ${unit}</span><span class="map-gradient"></span><span>${fmt(high)} ${unit}</span><span>Серый: нет данных · обводка: выбор</span>`;
  $("scatter").querySelectorAll(".map-country").forEach(el => {
    el.addEventListener("click", () => chooseCountry(el.dataset.country));
    el.addEventListener("keydown", e => {
      if (["Enter", " "].includes(e.key)) {
        e.preventDefault();
        chooseCountry(el.dataset.country);
      }
    });
  });
}

function renderTrend() {
  const rows = atlas.panel.filter(r => r.iso3 === state.country).sort((a, b) => a.year - b.year),
    valid = rows.filter(r => r[state.metric] != null);
  if (!valid.length) {
    $("trend").innerHTML = '<p class="empty">Нет данных по показателю.</p>';
    return;
  }
  const w = 330,
    h = 145,
    m = {
      l: 35,
      r: 16,
      t: 18,
      b: 25
    };
  const low = Math.max(0, Math.floor(Math.min(...valid.map(r => r[state.metric])) * .85)),
    high = Math.ceil(Math.max(...valid.map(r => r[state.metric])) * 1.1);
  const x = year => m.l + (year - 2010) / 13 * (w - m.l - m.r),
    y = v => h - m.b - (v - low) / (high - low) * (h - m.t - m.b);
  let body = "",
    segment = [];
  for (const v of [low, (low + high) / 2, high]) body += `<line x1="${m.l}" x2="${w-m.r}" y1="${y(v)}" y2="${y(v)}" class="svg-grid"/><text x="${m.l-6}" y="${y(v)+3}" text-anchor="end" class="svg-small">${fmt(v)}</text>`;
  const flush = () => {
    if (segment.length) body += `<polyline points="${segment.join(" ")}" fill="none" stroke="${colors.teal}" stroke-width="2.3"/>`;
    segment = [];
  };
  for (const r of rows) {
    if (r[state.metric] == null) {
      flush();
      continue;
    }
    segment.push(`${x(r.year)},${y(r[state.metric])}`);
  }
  flush();
  for (const r of valid) {
    const selected = r.year === state.year;
    body += `<circle cx="${x(r.year)}" cy="${y(r[state.metric])}" r="${selected?4.5:2}" fill="${selected?colors.orange:colors.teal}"><title>${r.year}: ${fmt(r[state.metric],1)}</title></circle>`;
  }
  for (const yr of [2010, 2016, 2023]) body += `<text x="${x(yr)}" y="${h-5}" class="svg-small" text-anchor="middle">${yr}</text>`;
  $("trend").innerHTML = svg(w, h, body, `Динамика: ${current().country}`);
}

function renderPeers() {
  const target = current(),
    rows = yearRows().filter(r => r.gdp_ppp_constant > 0 && r.age65_pct != null && r[state.metric] != null);
  if (!target.gdp_ppp_constant || target.age65_pct == null) {
    $("peers").innerHTML = '<p class="empty">Недостаточно данных для подбора аналогов.</p>';
    return;
  }
  const sd = a => Math.sqrt(mean(a.map(v => (v - mean(a)) ** 2))) || 1,
    sg = sd(rows.map(r => Math.log(r.gdp_ppp_constant))),
    sa = sd(rows.map(r => r.age65_pct));
  const peers = rows.filter(r => r.iso3 !== state.country).map(r => ({
    ...r,
    distance: ((Math.log(r.gdp_ppp_constant) - Math.log(target.gdp_ppp_constant)) / sg) ** 2 + ((r.age65_pct - target.age65_pct) / sa) ** 2
  })).sort((a, b) => a.distance - b.distance).slice(0, 5);
  const group = [target, ...peers],
    max = Math.max(...group.map(r => r[state.metric] || 0));
  $("peers").innerHTML = group.map(r => `<div class="peer ${r.iso3===state.country?"selected":""}"><button data-peer="${r.iso3}" title="${esc(r.country)}">${esc(r.country)}</button><div class="bar-track"><i style="width:${(r[state.metric]||0)/max*100}%"></i></div><b>${r[state.metric]==null?"н/д":fmt(r[state.metric])}</b></div>`).join("");
  $("peers").querySelectorAll("button").forEach(b => b.addEventListener("click", () => chooseCountry(b.dataset.peer)));
}

function renderResearch() {
  const rows = atlas.associations.estimates,
    w = 620,
    h = 310,
    m = {
      l: 177,
      r: 25,
      t: 25,
      b: 37
    };
  const lo = Math.min(-1, ...rows.map(r => r.change_10pct_low)) * 1.15,
    hi = Math.max(1, ...rows.map(r => r.change_10pct_high)) * 1.15;
  const x = v => m.l + (v - lo) / (hi - lo) * (w - m.l - m.r);
  let body = `<line x1="${x(0)}" x2="${x(0)}" y1="${m.t-10}" y2="${h-m.b}" stroke="${colors.orange}" stroke-dasharray="3 4"/>`;
  const labels = ["Объединённая модель", "Эффекты стран и лет", "Период до 2020", "Высокий доход", "Тренды стран"];
  rows.forEach((r, i) => {
    const y = 40 + i * 46,
      c = i === 1 ? colors.orange : colors.teal;
    body += `<text x="${m.l-15}" y="${y+4}" text-anchor="end" class="svg-label">${labels[i]}</text><line x1="${x(r.change_10pct_low)}" x2="${x(r.change_10pct_high)}" y1="${y}" y2="${y}" stroke="${c}" stroke-width="2"/><circle cx="${x(r.change_10pct)}" cy="${y}" r="5" fill="${c}"><title>${labels[i]}: ${fmt(r.change_10pct,2)}%, 95% ДИ ${fmt(r.change_10pct_low,2)} - ${fmt(r.change_10pct_high,2)}; n=${r.n}</title></circle>`;
  });
  for (let i = 0; i <= 4; i++) {
    const v = lo + (hi - lo) * i / 4;
    body += `<text x="${x(v)}" y="${h-20}" text-anchor="middle" class="svg-label">${fmt(v,1)}%</text>`;
  }
  $("forest").innerHTML = svg(w, h, body, "Устойчивость связи расходов и смертности, 95% доверительные интервалы");
  const change = Number($("spend-change").value),
    m0 = atlas.associations.main,
    ratio = 1 + change / 100;
  const effect = (ratio ** m0.coefficient - 1) * 100,
    ci = [(ratio ** m0.ci_low - 1) * 100, (ratio ** m0.ci_high - 1) * 100].sort((a, b) => a - b);
  $("change-label").textContent = `${change>0?"+":""}${change}%`;
  const row = current();
  $("scenario-result").innerHTML = `<div class="scenario-number">${effect>0?"+":""}${fmt(effect,2)}%</div><p class="scenario-detail">Связанное изменение смертности<br>95% ДИ: ${fmt(ci[0],2)}% - ${fmt(ci[1],2)}%</p><p class="scenario-baseline">${esc(row.country)}, ${state.year}<br>${row.treatable!=null?`Точка отсчёта: ${fmt(row.treatable,1)} → ${fmt(row.treatable*(1+effect/100),1)} на 100 000`:"Для точки отсчёта нет данных о смертности."}</p>`;
  $("scenario-help").textContent = `Расходы ${change > 0 ? "+" : ""}${change}% — изменение относительно выбранного года. По модели с ним связано изменение смертности ${effect > 0 ? "+" : ""}${fmt(effect, 2)}%: минус означает снижение, плюс — рост. 95% ДИ от ${fmt(ci[0], 2)}% до ${fmt(ci[1], 2)}% показывает неопределённость оценки.${ci[0] <= 0 && ci[1] >= 0 ? " Интервал включает ноль: данные совместимы с отсутствием изменения." : ""} Это относительное изменение показателя, а не процентные пункты и не доказанный эффект бюджета.`;

}

function renderForecast() {
  const f = atlas.forecast,
    selected = f.metrics.find(r => r.selected),
    base = f.metrics.find(r => r.model === "Persistence");
  $("model-kpis").innerHTML = kpi("Выбор по валидации", esc(f.selected_model), "Модель с наименьшей ошибкой на валидации") + kpi("MAE на тесте", fmt(selected.test_mae, 2), "Средняя ошибка на 100 тыс. · меньше лучше") + kpi("Изменение MAE к базе", `${fmt((selected.test_mae/base.test_mae-1)*100,1)}%`, "К прогнозу по прошлому году · минус лучше") + kpi("Покрытие интервала", `${fmt(selected.interval_coverage*100,1)}%`, "Доля фактов внутри интервала · цель 90%");
  const relativeError = (selected.test_mae / base.test_mae - 1) * 100;
  $("forecast-help").innerHTML = `<p><b>MAE ${fmt(selected.test_mae, 2)}:</b> среднее абсолютное отклонение прогноза от факта — ${fmt(selected.test_mae, 2)} смерти на 100 тыс. Это не проценты.</p><p><b>${fmt(relativeError, 1)}% к базе:</b> ошибка модели ${fmt(selected.test_mae, 2)} против ${fmt(base.test_mae, 2)} у прогноза по прошлому году. Отрицательный процент означает снижение ошибки.</p><p><b>Покрытие ${fmt(selected.interval_coverage * 100, 1)}%:</b> доля фактических значений, попавших в прогнозные интервалы. Цель — 90%; высокое покрытие может быть следствием широких интервалов.</p>`;
  $("model-table").innerHTML = f.metrics.map(r => `<tr class="${r.selected?"selected":""}"><td>${esc(r.model)}${r.selected?'<span class="model-tag">ВЫБРАНА ПО ВАЛИДАЦИИ</span>':""}</td><td>${fmt(r.validation_mae,2)}</td><td>${fmt(r.test_mae,2)}</td><td>${fmt(r.interval_coverage*100,1)}%</td></tr>`).join("");
  $("prediction-country").textContent = current().country;
  const predictions = atlas.predictions.filter(r => r.iso3 === state.country);
  $("predictions").innerHTML = predictions.length ? predictions.map(r => `<div class="prediction-row"><span>${r.year} ГОД</span><div class="prediction-values"><b>${fmt(r.actual,1)}<small>Факт · на 100 тыс.</small></b><b>${fmt(r.predicted,1)}<small>Прогноз · на 100 тыс.</small></b></div><small>Интервал: ${fmt(r.lower,1)} - ${fmt(r.upper,1)} на 100 000</small></div>`).join("") : '<p class="empty">Для этой страны нет полных тестовых наблюдений.</p>';
}

function renderData() {
  const query = $("search").value.toLowerCase().trim();
  const rows = yearRows().filter(r => `${r.country} ${r.iso3}`.toLowerCase().includes(query)).sort((a, b) => a.country.localeCompare(b.country));
  $("data-table").innerHTML = rows.length ? rows.map(r => `<tr class="${r.iso3===state.country?"selected":""}"><td>${esc(r.country)} <small>${r.iso3}</small></td><td>${r.year}</td><td>${fmt(r.spend_ppp)}</td><td>${fmt(r[state.metric],1)}</td><td>${fmt(r.gdp_ppp_constant)}</td><td>${fmt(r.age65_pct,1)}</td></tr>`).join("") : '<tr><td colspan="6">Страна не найдена</td></tr>';
  $("table-outcome").textContent = state.metric === "treatable" ? "Лечение, на 100 тыс." : state.metric === "preventable" ? "Профилактика, на 100 тыс." : "Предотвратимая, на 100 тыс.";
  $("quality-note").textContent = `${rows.length} стран за ${state.year} год. Во всём срезе: ${atlas.quality.mortality_rows} строк с исходом из ${atlas.quality.grid_rows}. SHA-256 всех ${atlas.quality.source_files} исходных файлов проверены при сборке.`;
}

function render() {
  if (state.view === "overview") renderOverview();
  if (state.view === "research") renderResearch();
  if (state.view === "forecast") renderForecast();
  if (state.view === "data") renderData();
}

async function boot() {
  try {
    async function loadData(name) {
      const embedded = document.getElementById(`embedded-${name}`);
      if (embedded) return JSON.parse(embedded.textContent);
      const response = await fetch(`data/${name}.json`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }
    [atlas, world] = await Promise.all([loadData("atlas"), loadData("world")]);
    const countries = [...new Map(atlas.panel.map(r => [r.iso3, r])).values()].sort((a, b) => a.country.localeCompare(b.country));
    for (const r of countries) {
      const option = document.createElement("option");
      option.value = r.iso3;
      option.textContent = r.country;
      $("country").append(option);
    }
    for (let yr = 2023; yr >= 2010; yr--) {
      const option = document.createElement("option");
      option.value = yr;
      option.textContent = yr;
      $("year").append(option);
    }
    $("country").value = state.country;
    $("year").value = state.year;
    $("country").addEventListener("change", e => chooseCountry(e.target.value));
    $("year").addEventListener("change", e => {
      state.year = Number(e.target.value);
      render();
    });
    $("metric").addEventListener("change", e => {
      state.metric = e.target.value;
      render();
    });
    $("spend-change").addEventListener("input", renderResearch);
    document.querySelectorAll("[data-chart]").forEach(button => button.addEventListener("click", () => {
      state.chart = button.dataset.chart;
      document.querySelectorAll("[data-chart]").forEach(b => {
        b.classList.toggle("active", b.dataset.chart === state.chart);
        b.setAttribute("aria-pressed", String(b.dataset.chart === state.chart));
      });
      renderOverview();
    }));
    $("map-variable").addEventListener("change", renderOverview);
    $("search").addEventListener("input", renderData);
    document.querySelectorAll(".nav-item").forEach(el => el.addEventListener("click", () => setView(el.dataset.view)));
    document.querySelectorAll("[data-jump]").forEach(el => el.addEventListener("click", () => {
      setView(el.dataset.jump);
      window.scrollTo({
        top: 0,
        behavior: "smooth"
      });
    }));
    window.addEventListener("hashchange", () => setView(location.hash.slice(1)));
    const dates = atlas.sources.map(s => s.retrieved_at_utc.slice(0, 10)).sort();
    $("snapshot-date").textContent = `Срез загружен: ${dates.at(-1)} · данные до 2023`;
    $("application").hidden = false;
    $("loading").hidden = true;
    setView(location.hash.slice(1) || "overview");
  } catch (error) {
    $("loading").textContent = "Не удалось загрузить срез. Запустите приложение через python -m healthvalue serve. Подробности: " + error.message;
  }
}
boot();
