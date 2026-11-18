/** Visual editor for custom:heizwerk-card (uses HA's ha-form). */
import { LitElement, html, nothing, type TemplateResult } from "lit";

interface EditorConfig {
  type: string;
  variant?: string;
  entity?: string;
  entities?: string[];
  title?: string;
  dial_min?: number;
  dial_max?: number;
  manual_duration?: string | number;
}

const SCHEMA = (de: boolean) => [
  {
    name: "variant",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: "standard", label: de ? "Standard (Raumkarte)" : "Standard (room card)" },
          {
            value: "compact",
            label: de ? "Kompakt (Kachel / Hausliste)" : "Compact (tile / house list)",
          },
        ],
      },
    },
  },
  { name: "entity", selector: { entity: { domain: "climate", integration: "heizwerk" } } },
  {
    name: "entities",
    selector: { entity: { domain: "climate", integration: "heizwerk", multiple: true } },
  },
  { name: "title", selector: { text: {} } },
  {
    type: "grid",
    name: "",
    schema: [
      { name: "dial_min", selector: { number: { min: 0, max: 30, step: 1, mode: "box" } } },
      { name: "dial_max", selector: { number: { min: 5, max: 35, step: 1, mode: "box" } } },
    ],
  },
  {
    name: "manual_duration",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: "next", label: de ? "Bis nächster Block" : "Until next block" },
          { value: "60", label: de ? "1 Stunde" : "1 hour" },
          { value: "180", label: de ? "3 Stunden" : "3 hours" },
        ],
      },
    },
  },
];

const LABELS: Record<string, [string, string]> = {
  variant: ["Variante", "Variant"],
  entity: ["Raum (Einzelkarte / Kachel)", "Room (single card / tile)"],
  entities: ["Räume (Hausliste, nur kompakt)", "Rooms (house list, compact only)"],
  title: ["Titel (Hausliste)", "Title (house list)"],
  dial_min: ["Skala von", "Scale from"],
  dial_max: ["Skala bis", "Scale to"],
  manual_duration: ["Dauer für ± (Standardkarte)", "Duration for ± (standard card)"],
};

export class HeizwerkCardEditor extends LitElement {
  static properties = { hass: { attribute: false }, _config: { state: true } };

  hass?: { locale?: { language?: string } };
  private _config?: EditorConfig;

  setConfig(config: EditorConfig): void {
    this._config = config;
  }

  private get _de(): boolean {
    return (this.hass?.locale?.language ?? "en").startsWith("de");
  }

  protected render(): TemplateResult | typeof nothing {
    if (!this.hass || !this._config) return nothing;
    if (!customElements.get("ha-form")) {
      return html`<p>
        ${this._de ? "Bitte im YAML-Modus bearbeiten." : "Please use the YAML editor."}
      </p>`;
    }
    const data = {
      variant: "standard",
      ...this._config,
      manual_duration: String(this._config.manual_duration ?? "next"),
    };
    return html`<ha-form
      .hass=${this.hass}
      .data=${data}
      .schema=${SCHEMA(this._de)}
      .computeLabel=${(s: { name: string }) => LABELS[s.name]?.[this._de ? 0 : 1] ?? s.name}
      @value-changed=${this._changed}
    ></ha-form>`;
  }

  private _changed(ev: CustomEvent<{ value: EditorConfig }>): void {
    const value = { ...ev.detail.value };
    const md = value.manual_duration;
    if (md === "60" || md === "180") value.manual_duration = Number(md);
    if (!value.entities?.length) delete value.entities;
    if (!value.title) delete value.title;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: value },
        bubbles: true,
        composed: true,
      }),
    );
  }
}

if (!customElements.get("heizwerk-card-editor")) {
  customElements.define("heizwerk-card-editor", HeizwerkCardEditor);
}
