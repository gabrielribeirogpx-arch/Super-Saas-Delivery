"use client";

import { useEffect, useMemo, useState } from "react";

import { CartItemWithModifiers, PublicMenuItem, SelectedModifier } from "@/components/storefront/types";

import styles from "./ItemDetailSheet.module.css";

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

  useEffect(() => {
    if (!item) return;
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [item, onClose]);

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
      <div className={styles.backdrop} onClick={onClose} aria-hidden="true" />
      <section className={styles.sheet} role="dialog" aria-modal="true" aria-labelledby="item-detail-title">
        <div className={styles.handle} />
        <div className={styles.header}>
          <div>
            <h2 id="item-detail-title">{item.name}</h2>
            <strong>R$ {(item.price_cents / 100).toFixed(2).replace(".", ",")}</strong>
            {item.description ? <p>{item.description}</p> : null}
          </div>
          <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Fechar personalização">×</button>
        </div>

        {(item.modifier_groups ?? []).map((group) => (
          <div key={group.id} className={styles.group}>
            <div className={styles.groupHeading}>
              <strong>{group.name}</strong>
              <span>{group.required || group.min_selection > 0 ? "OBRIGATÓRIO" : "OPCIONAL"}</span>
            </div>

            {getGroupControlType(group) === "single"
              ? group.options.map((opt) => (
                  <button type="button" key={opt.id} className={`${styles.option} ${singleSelections[group.id] === opt.id ? styles.selectedOption : ""}`} onClick={() => setSingleSelections((prev) => ({ ...prev, [group.id]: prev[group.id] === opt.id ? null : opt.id }))}>
                    <span>{opt.name}</span>
                    {Number(opt.price_delta) > 0 ? <span>+R$ {Number(opt.price_delta).toFixed(2).replace(".", ",")}</span> : null}
                  </button>
                ))
              : group.options.map((opt) => {
                  const currentQty = qtySelections[group.id]?.[opt.id] || 0;
                  const groupTotal = Object.values(qtySelections[group.id] || {}).reduce((s, v) => s + v, 0);
                  const atMax = groupTotal >= group.max_selection;
                  return (
                    <div key={opt.id} className={styles.option}>
                      <span>{opt.name}</span>
                      <div className={styles.stepper}>
                        <button type="button" aria-label={`Remover ${opt.name}`} onClick={() => setQtySelections((prev) => {
                          const next = { ...(prev[group.id] || {}) };
                          next[opt.id] = Math.max(0, (next[opt.id] || 0) - 1);
                          return { ...prev, [group.id]: next };
                        })} disabled={currentQty === 0}>−</button>
                        <span>{currentQty}</span>
                        <button type="button" aria-label={`Adicionar ${opt.name}`} onClick={() => setQtySelections((prev) => {
                          if (atMax) return prev;
                          const next = { ...(prev[group.id] || {}) };
                          next[opt.id] = (next[opt.id] || 0) + 1;
                          return { ...prev, [group.id]: next };
                        })} disabled={atMax || currentQty >= group.max_selection}>+</button>
                      </div>
                    </div>
                  );
                })}
          </div>
        ))}

        <div className={styles.note}>
          <label htmlFor="item-note">Alguma observação?</label>
          <textarea id="item-note" value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="Ex.: tirar cebola" />
        </div>

        <div className={styles.bottomSpacer} />
      </section>

      <div className={styles.actions}>
        <div className={styles.quantity}>
          <button type="button" aria-label="Diminuir quantidade" onClick={() => setQty((q) => Math.max(1, q - 1))}>−</button>
          <span>{qty}</span>
          <button type="button" aria-label="Aumentar quantidade" onClick={() => setQty((q) => q + 1)}>+</button>
        </div>
        <button type="button" className={styles.addButton} onClick={handleAddToCart} disabled={!valid}>
          {valid ? `Adicionar · R$ ${totalPrice.toFixed(2).replace(".", ",")}` : "Selecione as opções obrigatórias"}
        </button>
      </div>
    </>
  );
}
