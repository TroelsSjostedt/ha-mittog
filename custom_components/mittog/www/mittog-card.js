/**
 * MitTog card — the platform display, on your dashboard.
 *
 * Reads one watched-departure sensor (sensor.<name>_departure) and draws the
 * board the way the sign above the track draws it: the train turned the way it
 * physically stands, with the nose at the end it will leave towards.
 *
 * Deliberately dark in both themes — it is a platform display, not a document.
 */

const VERSION = "0.2.0";

// The feed lists cars front-first (verified on the platform at Vordingborg,
// 7 Sep 2026). On Sydbanen the platform runs Nykøbing F on the left and
// København on the right, so a DOWN train (towards København) has its nose on
// the right and the strip is drawn in reverse.
const NOSE_RIGHT = "DOWN";

const STATUS_TEXT = {
  til_tiden: "Til tiden",
  forsinket: "Forsinket",
  aflyst: "Aflyst",
  planlagt: "Planlagt",
  afgaaet: "Afgået",
  ikke_i_feed: "Ikke i feedet",
};

const CSS = `
:host { display: block; }
.card {
  background: #14213D;
  color: #F3F1EC;
  border-radius: 16px;
  padding: 18px 20px 16px;
  font-family: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  box-shadow: 0 8px 28px rgba(0,0,0,.18);
  overflow: hidden;
}
.head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.name {
  font-weight: 700; font-size: 15px; letter-spacing: .12em;
  text-transform: uppercase; opacity: .7;
}
.live { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; opacity: .55; white-space: nowrap; }
.live::before {
  content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #3DBE5B; margin-right: 6px; vertical-align: 1px;
}
.live.down::before { background: #C8102E; }

.main { display: grid; grid-template-columns: auto 1fr auto; gap: 18px; align-items: end; margin-top: 10px; }
.time { font-weight: 800; font-size: 60px; line-height: .9; font-variant-numeric: tabular-nums; }
.time small { display: block; font-size: 13px; font-weight: 500; letter-spacing: .08em; opacity: .6; margin-top: 6px; text-transform: uppercase; }
.time s { color: #F3F1EC; opacity: .45; font-size: 26px; display: block; font-weight: 700; margin-bottom: -2px; }
.time.late { color: #F2C230; }
.time.off { color: #C8102E; }

.dest { font-weight: 700; font-size: 26px; line-height: 1.1; min-width: 0; }
.badge {
  display: inline-block; background: #3DBE5B; color: #0B2A12; font-size: 13px;
  padding: 2px 8px; border-radius: 4px; letter-spacing: .06em; margin-bottom: 6px; font-weight: 700;
}
.badge.ic { background: #C8102E; color: #fff; }
.dest .to { display: block; overflow-wrap: anywhere; }
.sub { display: block; font-weight: 400; font-size: 13px; opacity: .65; margin-top: 3px; }

.track { text-align: center; border: 2px solid #F3F1EC; border-radius: 10px; padding: 6px 12px; min-width: 54px; }
.track b { display: block; font-size: 32px; line-height: 1; font-weight: 800; font-variant-numeric: tabular-nums; }
.track small { font-size: 11px; letter-spacing: .14em; opacity: .7; }
.track.changed { border-color: #F2C230; color: #F2C230; }
.track.changed small { opacity: 1; }

.strip { margin-top: 26px; }
.train { display: flex; gap: 3px; align-items: flex-end; }
.train.rev { flex-direction: row-reverse; }
.car {
  flex: 1; position: relative; height: 42px; border: 2.5px solid #F3F1EC; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 21px; font-variant-numeric: tabular-nums; min-width: 0;
}
.car.nose { border-radius: 20px 6px 6px 6px; }
.train.rev .car.nose { border-radius: 6px 20px 6px 6px; }
.car.nose::after {
  content: ""; position: absolute; top: 50%; left: -14px; transform: translateY(-50%);
  width: 0; height: 0; border: 7px solid transparent; border-right-color: #C8102E;
}
.train.rev .car.nose::after {
  left: auto; right: -14px; border-right-color: transparent; border-left-color: #C8102E;
}
.tags { position: absolute; top: -13px; left: 0; right: 0; display: flex; justify-content: center; gap: 3px; }
.tag {
  width: 20px; height: 20px; border-radius: 50%; background: #F3F1EC; color: #14213D;
  font: 700 11px/20px "IBM Plex Sans", Arial, sans-serif; text-align: center;
}
.tag.f { background: #F2C230; color: #14213D; }
.tag.b { background: #3DBE5B; color: #0B2A12; }
.rail { height: 4px; background: #F3F1EC; opacity: .25; border-radius: 2px; margin-top: 6px; }

.dir {
  display: flex; align-items: baseline; justify-content: space-between; gap: 14px; margin-top: 9px;
  font: 600 11px/1.3 "IBM Plex Sans", Arial, sans-serif; letter-spacing: .09em;
  text-transform: uppercase; color: rgba(243,241,236,.6);
}
.dir .go { display: inline-flex; align-items: baseline; gap: 7px; font-weight: 700; color: #F3F1EC; min-width: 0; }
.dir .go em { font-style: normal; color: #C8102E; font-size: 14px; letter-spacing: 0; }
.dir .n { font-size: 15px; font-weight: 800; font-variant-numeric: tabular-nums; }
.dir .dest-inline { overflow-wrap: anywhere; }

.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 11.5px; color: rgba(243,241,236,.62); margin-top: 8px; }
.legend span::before {
  content: ""; display: inline-block; width: 9px; height: 9px; border-radius: 50%;
  margin-right: 5px; vertical-align: -1px; background: var(--dot);
}
.msg {
  margin-top: 14px; font-size: 13px; background: rgba(242,194,48,.14);
  border-left: 3px solid #F2C230; padding: 7px 10px; border-radius: 4px;
}
.msg.red { background: rgba(200,16,46,.2); border-color: #C8102E; }
.quiet { margin-top: 18px; font-size: 14px; opacity: .6; line-height: 1.5; }
.err { color: #F2C230; }
`;

const hhmm = (iso) => {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  return d.toLocaleTimeString("da-DK", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Copenhagen",
  });
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

class MitTogCard extends HTMLElement {
  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find((e) =>
      e.startsWith("sensor.") && e.endsWith("_departure")
    );
    return { entity: entity || "sensor.skift_mig_departure" };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Angiv en afgangs-sensor, fx entity: sensor.pa_arbejde_departure");
    }
    if (!config.entity.startsWith("sensor.")) {
      throw new Error("entity skal være en sensor fra MitTog");
    }
    this._config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._lastKey = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  _render() {
    if (!this._hass || !this._config) return;
    const st = this._hass.states[this._config.entity];

    // Only re-render when something we draw actually changed. The feed pushes
    // every few seconds; repainting on each push makes text unselectable.
    const key = st ? `${st.state}|${st.last_updated}` : "missing";
    if (key === this._lastKey) return;
    this._lastKey = key;

    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="card">${this._body(st)}</div>`;
  }

  _body(st) {
    const title = esc(this._config.name || st?.attributes?.friendly_name || "Afgang");

    if (!st) {
      return `<div class="head"><span class="name">${title}</span></div>
        <div class="quiet err">Sensoren <b>${esc(this._config.entity)}</b> findes ikke.</div>`;
    }

    const a = st.attributes || {};
    const station = a.station ? `Live · ${esc(a.station)}` : "Live";

    if (st.state === "unavailable") {
      return `<div class="head"><span class="name">${title}</span>
          <span class="live down">Ingen forbindelse</span></div>
        <div class="quiet err">Feedet har været tavst i over to minutter. Viser hellere ingenting end gamle tider som friske.</div>`;
    }

    if (a.status === "ikke_i_feed" || st.state === "unknown" || !a.tog) {
      const watched = a.overvaaget_tid ? ` ${esc(a.overvaaget_tid)}` : "";
      return `<div class="head"><span class="name">${title}</span>
          <span class="live">${station}</span></div>
        <div class="quiet">Toget${watched} er ikke på tavlen endnu.<br>
          Det dukker typisk op mange timer før afgang; prognosen kommer omkring tre kvarter før.</div>`;
    }

    const cancelled = a.aflyst === true;
    const delay = Number.isFinite(a.forsinkelse_min) ? a.forsinkelse_min : 0;
    const late = !cancelled && delay > 0;
    const planned = hhmm(a.planlagt);
    const expected = hhmm(a.forventet);

    let timeCls = "time";
    if (cancelled) timeCls += " off";
    else if (late) timeCls += " late";

    let timeInner;
    if (cancelled) {
      timeInner = `${esc(planned)}<small>Aflyst</small>`;
    } else if (late) {
      timeInner = `<s>${esc(planned)}</s>${esc(expected)}<small>+${delay} min</small>`;
    } else {
      timeInner = `${esc(expected || planned)}<small>${a.prognose ? "Til tiden" : "Planlagt"}</small>`;
    }

    const isIc = String(a.produkt || "").toUpperCase().startsWith("IC");
    const consist = [a.togsaet, a.vogne_antal ? `${a.vogne_antal} vogne` : null]
      .filter(Boolean)
      .join(" · ");

    const trackCls = a.spor_aendret ? "track changed" : "track";
    const trackLabel = a.spor_aendret && a.spor_oprindeligt
      ? `SPOR ↔ ${esc(a.spor_oprindeligt)}`
      : "SPOR";
    const track = `<div class="${trackCls}"><b>${esc(a.spor || "–")}</b><small>${trackLabel}</small></div>`;

    const head = `<div class="head"><span class="name">${title}</span>
        <span class="live">${station}</span></div>`;

    const main = `<div class="main">
        <div class="${timeCls}">${timeInner}</div>
        <div class="dest">
          <span class="badge${isIc ? " ic" : ""}">${esc(a.tog)}</span>
          <span class="to">${esc(a.destination || "")}</span>
          ${consist ? `<span class="sub">${esc(consist)}</span>` : ""}
        </div>
        ${track}
      </div>`;

    return head + main + this._strip(a) + this._message(a, cancelled);
  }

  _strip(a) {
    const cars = Array.isArray(a.vogne) ? a.vogne : [];
    if (!cars.length) {
      return `<div class="quiet">Vognsammensætningen er ikke meldt for dette tog.</div>`;
    }

    const first = new Set(a.foerste_klasse || []);
    const quiet = new Set(a.stillezone || []);
    const bikes = new Set(a.cykler || []);

    const boxes = cars
      .map((num, i) => {
        const tags = [];
        if (first.has(num)) tags.push('<span class="tag f">1</span>');
        if (quiet.has(num)) tags.push('<span class="tag">·</span>');
        if (bikes.has(num)) tags.push('<span class="tag b">⚲</span>');
        const cls = i === 0 ? "car nose" : i === cars.length - 1 ? "car tail" : "car";
        return `<div class="${cls}">${
          tags.length ? `<div class="tags">${tags.join("")}</div>` : ""
        }${esc(num)}</div>`;
      })
      .join("");

    // Nose points the way the train leaves. Towards København it sits on the
    // right, towards Nykøbing F on the left — matching mittog.dk's own drawing.
    const rev = a.retning === NOSE_RIGHT;
    const front = esc(a.forende ?? cars[0]);
    const rear = esc(a.bagende ?? cars[cars.length - 1]);
    const dest = esc(a.destination || "");

    const goSpan = `<span class="go">Forrest <span class="n">${front}</span> <em>${
      rev ? "→" : "←"
    }</em> <span class="dest-inline">${dest}</span></span>`;
    const rearSpan = `<span>Bagest <span class="n">${rear}</span></span>`;

    const dir = `<div class="dir">${rev ? rearSpan + goSpan : goSpan + rearSpan}</div>`;

    const legend = `<div class="legend">
        ${first.size ? '<span style="--dot:#F2C230">1. klasse</span>' : ""}
        ${quiet.size ? '<span style="--dot:#F3F1EC">Stillezone</span>' : ""}
        ${bikes.size ? '<span style="--dot:#3DBE5B">Cykler</span>' : ""}
        <span style="--dot:#C8102E">Forende</span>
      </div>`;

    return `<div class="strip">
        <div class="train${rev ? " rev" : ""}">${boxes}</div>
        <div class="rail"></div>
        ${dir}
        ${legend}
      </div>`;
  }

  _message(a, cancelled) {
    const lines = [];
    if (cancelled) lines.push("Toget er aflyst.");
    if (a.spor_aendret && a.spor_oprindeligt) {
      lines.push(`Sporet er ændret fra ${a.spor_oprindeligt} til ${a.spor}.`);
    }
    if (a.deler_sig) lines.push("Toget deler sig undervejs — tjek hvilken vogn der kører hvorhen.");
    if (a.bemaerkning) lines.push(String(a.bemaerkning));
    if (!lines.length) return "";
    return `<div class="msg${cancelled ? " red" : ""}">${esc(lines.join(" · "))}</div>`;
  }
}

if (!customElements.get("mittog-card")) {
  customElements.define("mittog-card", MitTogCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "mittog-card",
    name: "MitTog perronskærm",
    description: "Afgangstavle med togsæt, vognnumre og kørselsretning.",
    preview: false,
  });
  console.info(`%c MITTOG-CARD %c ${VERSION} `, "background:#14213D;color:#F3F1EC", "background:#C8102E;color:#fff");
}
