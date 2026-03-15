"use client";

import { useEffect, useMemo, useState } from "react";

import { CartItemWithModifiers, PublicMenuItem, SelectedModifier } from "@/components/storefront/types";

interface ItemDetailSheetProps {
  item: PublicMenuItem | null;
  onClose: () => void;
  onAddToCart: (cartItem: CartItemWithModifiers) => void;
  theme: "dark" | "white";
}

function getGroupControlType(group: NonNullable<PublicMenuItem["modifier_groups"]>[number]): "single" | "qty" {
  if (group.max_selection === 1) return "single";
  return "qty";
}

export function ItemDetailSheet({ item, onClose, onAddToCart }: ItemDetailSheetProps) {
  const [qty, setQty] = useState(1);
  const [singleSelections, setSingleSelections] = useState<Record<number, number | null>>({});
  const [qtySelections, setQtySelections] = useState<Record<number, Record<number, number>>>({});
  const [note, setNote] = useState("");

  useEffect(() => {
    if (item) {
      setQty(1);
      setSingleSelections({});
      setQtySelections({});
      setNote("");
    }
  }, [item?.id]);

  const valid = useMemo(() => {
    if (!item) return false;
    return (item.modifier_groups ?? []).every((group) => {
      if (!group.required && group.min_selection === 0) return true;
      const type = getGroupControlType(group);
      if (type === "single") return singleSelections[group.id] != null;
      const groupQty = qtySelections[group.id] || {};
      const total = Object.values(groupQty).reduce((s, v) => s + v, 0);
      return total >= group.min_selection;
    });
  }, [item, qtySelections, singleSelections]);

  const totalPrice = useMemo(() => {
    if (!item) return 0;
    let extrasCents = 0;
    (item.modifier_groups ?? []).forEach((group) => {
      const type = getGroupControlType(group);
      if (type === "single") {
        const optionId = singleSelections[group.id];
        const option = group.options.find((opt) => opt.id === optionId);
        if (option) extrasCents += Math.round(Number(option.price_delta) * 100);
      } else {
        const groupQty = qtySelections[group.id] || {};
        group.options.forEach((opt) => {
          extrasCents += (groupQty[opt.id] || 0) * Math.round(Number(opt.price_delta) * 100);
        });
      }
    });
    return ((item.price_cents + extrasCents) / 100) * qty;
  }, [item, qty, qtySelections, singleSelections]);

  function handleAddToCart() {
    if (!item || !valid) return;

    const selectedModifiers: SelectedModifier[] = [];
    (item.modifier_groups ?? []).forEach((group) => {
      const type = getGroupControlType(group);
      if (type === "single") {
        const optionId = singleSelections[group.id];
        const option = group.options.find((opt) => opt.id === optionId);
        if (option) {
          selectedModifiers.push({
            groupId: group.id,
            groupName: group.name,
            optionId: option.id,
            optionName: option.name,
            price: Number(option.price_delta),
            quantity: 1,
          });
        }
      } else {
        const groupQty = qtySelections[group.id] || {};
        group.options.forEach((option) => {
          const optionQty = groupQty[option.id] || 0;
          if (optionQty > 0) {
            selectedModifiers.push({
              groupId: group.id,
              groupName: group.name,
              optionId: option.id,
              optionName: option.name,
              price: Number(option.price_delta),
              quantity: optionQty,
            });
          }
        });
      }
    });

    onAddToCart({
      id: `${item.id}-${Date.now()}`,
      menuItemId: item.id,
      name: item.name,
      price: item.price_cents / 100,
      quantity: qty,
      modifiers: selectedModifiers,
      note: note.trim(),
      totalPrice,
    });
  }

  if (!item) return null;

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", zIndex: 100 }} />
      <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, maxHeight: "92vh", background: "var(--bg-page)", borderRadius: "20px 20px 0 0", overflowY: "auto", zIndex: 101 }}>
        <div style={{ width: 40, height: 4, background: "var(--border-medium)", borderRadius: 2, margin: "12px auto 0" }} />
        <div style={{ padding: "16px 20px 8px" }}>
          <h2 style={{ margin: 0 }}>{item.name}</h2>
          {item.description ? <p style={{ margin: "6px 0 0" }}>{item.description}</p> : null}
        </div>

        {(item.modifier_groups ?? []).map((group) => (
          <div key={group.id} style={{ borderTop: "1px solid var(--border-default)", padding: "16px 20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span>{group.name}</span>
              <span>{group.required ? "OBRIGATÓRIO" : "OPCIONAL"}</span>
            </div>

            {getGroupControlType(group) === "single"
              ? group.options.map((opt) => (
                  <div key={opt.id} onClick={() => setSingleSelections((prev) => ({ ...prev, [group.id]: prev[group.id] === opt.id ? null : opt.id }))} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", cursor: "pointer" }}>
                    <span>{opt.name}</span>
                    {Number(opt.price_delta) > 0 ? <span>+R$ {Number(opt.price_delta).toFixed(2).replace(".", ",")}</span> : null}
                  </div>
                ))
              : group.options.map((opt) => {
                  const currentQty = qtySelections[group.id]?.[opt.id] || 0;
                  const groupTotal = Object.values(qtySelections[group.id] || {}).reduce((s, v) => s + v, 0);
                  const atMax = groupTotal >= group.max_selection;
                  return (
                    <div key={opt.id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0" }}>
                      <span>{opt.name}</span>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <button onClick={() => setQtySelections((prev) => {
                          const next = { ...(prev[group.id] || {}) };
                          next[opt.id] = Math.max(0, (next[opt.id] || 0) - 1);
                          return { ...prev, [group.id]: next };
                        })} disabled={currentQty === 0}>−</button>
                        <span>{currentQty}</span>
                        <button onClick={() => setQtySelections((prev) => {
                          if (atMax && currentQty === 0) return prev;
                          const next = { ...(prev[group.id] || {}) };
                          next[opt.id] = (next[opt.id] || 0) + 1;
                          return { ...prev, [group.id]: next };
                        })} disabled={(atMax && currentQty === 0) || currentQty >= group.max_selection}>+</button>
                      </div>
                    </div>
                  );
                })}
          </div>
        ))}

        <div style={{ padding: "16px 20px", borderTop: "1px solid var(--border-default)" }}>
          <label style={{ display: "block", marginBottom: 8 }}>Alguma observação?</label>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} style={{ width: "100%" }} />
        </div>

        <div style={{ height: 120 }} />
      </div>

      <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, background: "var(--bg-page)", borderTop: "1px solid var(--border-default)", padding: "12px 20px 24px", zIndex: 102 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16, marginBottom: 12 }}>
          <button onClick={() => setQty((q) => Math.max(1, q - 1))}>−</button>
          <span>{qty}</span>
          <button onClick={() => setQty((q) => q + 1)}>+</button>
        </div>
        <button onClick={handleAddToCart} disabled={!valid} style={{ width: "100%", height: 50 }}>
          {valid ? `Adicionar · R$ ${totalPrice.toFixed(2).replace(".", ",")}` : "Selecione as opções obrigatórias"}
        </button>
      </div>
    </>
  );
}
