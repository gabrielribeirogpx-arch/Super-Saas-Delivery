"use client";

import { useEffect, useState } from "react";

import { useAppearance, type AppearanceSettings } from "@/hooks/useAppearance";

function applyCSSVariables(theme: AppearanceSettings) {
  document.documentElement.style.setProperty("--primary-color", theme.primary_color);
  document.documentElement.style.setProperty("--secondary-color", theme.secondary_color);
  document.documentElement.style.setProperty("--button-radius", `${theme.button_radius}px`);
  document.documentElement.style.setProperty("--font-family", theme.font_family);
}

export default function AppearancePanel() {
  const { appearance, setAppearance, saveAppearance, loading } = useAppearance();
  const [status, setStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    applyCSSVariables(appearance);
  }, [appearance]);

  const handleSave = async () => {
    setIsSaving(true);
    setStatus(null);
    try {
      await saveAppearance(appearance);
      setStatus("Aparência salva com sucesso.");
    } catch {
      setStatus("Não foi possível salvar a aparência.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="appearance-wrapper">
      <div className="appearance-form">
        <h2 className="appearance-title">Aparência da Loja</h2>

        <label htmlFor="primary-color">Cor Primária</label>
        <input
          id="primary-color"
          type="color"
          value={appearance.primary_color}
          onChange={(event) =>
            setAppearance({ ...appearance, primary_color: event.target.value })
          }
        />

        <label htmlFor="secondary-color">Cor Secundária</label>
        <input
          id="secondary-color"
          type="color"
          value={appearance.secondary_color}
          onChange={(event) =>
            setAppearance({ ...appearance, secondary_color: event.target.value })
          }
        />

        <label htmlFor="button-radius">Raio do Botão ({appearance.button_radius}px)</label>
        <input
          id="button-radius"
          type="range"
          min="4"
          max="32"
          value={appearance.button_radius}
          onChange={(event) =>
            setAppearance({ ...appearance, button_radius: Number(event.target.value) })
          }
        />

        <label htmlFor="font-family">Fonte</label>
        <input
          id="font-family"
          type="text"
          value={appearance.font_family}
          onChange={(event) =>
            setAppearance({ ...appearance, font_family: event.target.value })
          }
        />

        <label htmlFor="layout-variant">Layout</label>
        <select
          id="layout-variant"
          value={appearance.layout_variant}
          onChange={(event) =>
            setAppearance({
              ...appearance,
              layout_variant: event.target.value as AppearanceSettings["layout_variant"],
            })
          }
        >
          <option value="clean">Clean</option>
          <option value="modern">Modern</option>
          <option value="commercial">Commercial</option>
        </select>

        <button disabled={isSaving || loading} onClick={handleSave} type="button">
          {isSaving ? "Salvando..." : "Salvar"}
        </button>

        {status && <p className="appearance-status">{status}</p>}
      </div>

      <div className="appearance-preview">
        <h3>Preview</h3>
        <p>Atualização em tempo real conforme você ajusta as configurações.</p>
        <div className="preview-card">
          <h4>Produto Premium</h4>
          <span>R$ 39,90</span>
          <button className="preview-button" type="button">
            Botão exemplo
          </button>
        </div>
      </div>
    </div>
  );
}
