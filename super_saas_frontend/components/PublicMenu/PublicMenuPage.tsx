"use client";

import Image from "next/image";
import { CSSProperties, useEffect, useMemo, useState } from "react";

import { CheckoutModal } from "@/components/CheckoutModal";
import { ItemDetailSheet } from "@/components/ItemDetailSheet";
import { CartItemWithModifiers, PublicMenuCategory, PublicMenuItem, PublicMenuResponse } from "@/components/storefront/types";
import { formatCurrencyFromCents } from "@/lib/currency";

import styles from "./PublicMenu.module.css";

type ThemeMode = "white" | "dark";

interface PublicMenuPageProps {
  menu: PublicMenuResponse;
  enableCart?: boolean;
  forcedTheme?: ThemeMode;
  previewStyle?: CSSProperties;
  hideThemeToggle?: boolean;
}

const getItemBadge = (item: PublicMenuItem) => {
  if (item.featured || item.is_popular) return { label: "Bestseller", className: styles.badgeAccent };
  if ((item.tags ?? []).some((tag) => tag.toLowerCase() === "especial")) return { label: "Especial", className: styles.badgeGreen };
  if ((item.tags ?? []).some((tag) => tag.toLowerCase() === "novo")) return { label: "Novo", className: styles.badgeCoral };
  return null;
};

export function PublicMenuPage({ menu, enableCart = true, forcedTheme, previewStyle, hideThemeToggle = false }: PublicMenuPageProps) {
  const [theme, setTheme] = useState<ThemeMode>("white");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");
  const [cartItems, setCartItems] = useState<CartItemWithModifiers[]>([]);
  const [popItemId, setPopItemId] = useState<number | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState<PublicMenuItem | null>(null);

  const cartStorageKey = useMemo(() => `mobile-storefront-cart:${menu.slug}`, [menu.slug]);

  useEffect(() => {
    if (forcedTheme) {
      setTheme(forcedTheme);
      return;
    }

    const storedTheme = typeof window !== "undefined" ? localStorage.getItem("menu-theme") : null;
    if (storedTheme === "dark" || storedTheme === "white") setTheme(storedTheme);
  }, [forcedTheme]);

  useEffect(() => {
    if (forcedTheme) {
      return;
    }
    localStorage.setItem("menu-theme", theme);
  }, [forcedTheme, theme]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(cartStorageKey);
      if (!stored) return;
      const parsed = JSON.parse(stored) as CartItemWithModifiers[];
      if (Array.isArray(parsed)) {
        setCartItems(parsed);
      }
    } catch {
      // Ignora erro de parse para não quebrar o cardápio público.
    }
  }, [cartStorageKey]);

  useEffect(() => {
    window.localStorage.setItem(cartStorageKey, JSON.stringify(cartItems));
  }, [cartItems, cartStorageKey]);


  const normalizedSections = useMemo(() => {
    const sections = [...menu.categories];
    if (menu.items_without_category.length > 0) {
      sections.push({ id: -1, name: "Sem categoria", sort_order: Number.MAX_SAFE_INTEGER, items: menu.items_without_category });
    }
    return sections;
  }, [menu.categories, menu.items_without_category]);

  const filteredSections = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return normalizedSections
      .filter((section) => activeCategory === "all" || String(section.id) === activeCategory)
      .map((section) => ({
        ...section,
        items: section.items.filter((item) => {
          if (item.is_active === false || item.isAvailable === false) return false;
          if (!query) return true;
          return `${item.name} ${item.description ?? ""}`.toLowerCase().includes(query);
        }),
      }))
      .filter((section) => section.items.length > 0);
  }, [activeCategory, normalizedSections, searchQuery]);

  const allItems = useMemo(() => normalizedSections.flatMap((section) => section.items), [normalizedSections]);

  const highlightedItems = useMemo(() => {
    return [...allItems]
      .sort((a, b) => {
        const aScore = a.featured ? 100000 : a.orderCount ?? 0;
        const bScore = b.featured ? 100000 : b.orderCount ?? 0;
        return bScore - aScore;
      })
      .slice(0, 5);
  }, [allItems]);

  const quantityByItem = useMemo(
    () => cartItems.reduce<Record<number, number>>((acc, entry) => ({ ...acc, [entry.menuItemId]: acc[entry.menuItemId] ? acc[entry.menuItemId] + entry.quantity : entry.quantity }), {}),
    [cartItems],
  );

  const addToCart = (cartItem: CartItemWithModifiers) => {
    setCartItems((current) => [...current, cartItem]);
    setPopItemId(cartItem.menuItemId);
    window.setTimeout(() => setPopItemId(null), 220);
  };

  const handleItemClick = (item: PublicMenuItem) => {
    if (!item.modifier_groups || item.modifier_groups.length === 0) {
      addToCart({
        id: `${item.id}-${Date.now()}`,
        menuItemId: item.id,
        name: item.name,
        price: item.price_cents / 100,
        quantity: 1,
        modifiers: [],
        note: "",
        totalPrice: item.price_cents / 100,
      });
      return;
    }
    setSelectedItem(item);
  };

  const cartCount = cartItems.reduce((sum, entry) => sum + entry.quantity, 0);
  const cartTotal = cartItems.reduce((sum, entry) => sum + Math.round(entry.totalPrice * 100), 0);

  const hideDiscovery = searchQuery.trim().length > 0;

  return (
    <main className={styles.page} data-theme={theme} style={previewStyle}>
      <div className={styles.container}>
        <MenuHero
          coverUrl={menu.public_settings?.cover_image_url}
          avatarUrl={menu.public_settings?.logo_url}
          storeName={menu.tenant.name}
          slug={menu.slug}
          isOpen={Boolean(menu.tenant.is_open ?? menu.tenant.manual_open_status ?? true)}
          deliveryTime={menu.tenant.estimated_prep_time ?? "25-40 min"}
          theme={theme}
          onToggleTheme={() => setTheme((current) => (current === "white" ? "dark" : "white"))}
          hideThemeToggle={hideThemeToggle || Boolean(forcedTheme)}
        />

        <MenuInfoBar
          deliveryTime={menu.tenant.estimated_prep_time ?? "25-40 min"}
          deliveryFee="R$ 0,00"
          paymentMethods="Pix, Cartão"
        />

        <MenuSearch onSearch={setSearchQuery} searchQuery={searchQuery} />

        {!hideDiscovery && highlightedItems.length > 0 && <MenuHighlights items={highlightedItems} onAdd={handleItemClick} />}

        {!hideDiscovery && (
          <MenuCategoryNav
            categories={normalizedSections}
            activeCategory={activeCategory}
            onSelect={(id) => setActiveCategory(id)}
          />
        )}

        <MenuSections sections={filteredSections} onAdd={handleItemClick} quantityByItem={quantityByItem} popItemId={popItemId} />

        {filteredSections.length === 0 && <p className={styles.empty}>Nenhum item encontrado</p>}

        {enableCart && cartCount > 0 && <MenuCartBar itemCount={cartCount} total={cartTotal} onClick={() => setCheckoutOpen(true)} />}


        <CheckoutModal
          isOpen={checkoutOpen}
          onClose={() => setCheckoutOpen(false)}
          cartItems={cartItems}
          onOrderSuccess={() => {
            setCartItems([]);
            localStorage.removeItem(`mobile-storefront-cart:${menu.slug}`);
            setCheckoutOpen(false);
          }}
          tenant={{ slug: menu.slug, store_id: menu.tenant_id, name: menu.tenant.name }}
          theme={theme}
        />

        {selectedItem ? (
          <ItemDetailSheet
            item={selectedItem}
            onClose={() => setSelectedItem(null)}
            onAddToCart={(cartItem) => {
              addToCart(cartItem);
              setSelectedItem(null);
            }}
            theme={theme}
          />
        ) : null}

        <MenuFooter />
      </div>
    </main>
  );
}

function MenuThemeToggle({ onToggle, theme }: { onToggle: () => void; theme: ThemeMode }) {
  return (
    <button type="button" className={styles.toggle} onClick={onToggle} aria-label="Alternar tema">
      {theme === "white" ? <MoonIcon /> : <SunIcon />}
    </button>
  );
}

function MenuHero({
  coverUrl,
  avatarUrl,
  storeName,
  slug,
  isOpen,
  deliveryTime,
  theme,
  onToggleTheme,
  hideThemeToggle,
}: {
  coverUrl?: string | null;
  avatarUrl?: string | null;
  storeName: string;
  slug: string;
  isOpen: boolean;
  deliveryTime: string;
  theme: ThemeMode;
  onToggleTheme: () => void;
  hideThemeToggle?: boolean;
}) {
  return (
    <header className={styles.hero}>
      {coverUrl ? <Image src={coverUrl} alt={storeName} fill style={{ objectFit: "cover" }} /> : <PlaceholderIcon className={styles.heroFallback} />}
      <div className={styles.heroOverlay} />
      {hideThemeToggle ? null : <MenuThemeToggle onToggle={onToggleTheme} theme={theme} />}
      <div className={styles.heroContent}>
        <div className={styles.avatar}>
          {avatarUrl ? <Image src={avatarUrl} alt={`Logo ${storeName}`} width={58} height={58} /> : <PlaceholderIcon className={styles.imageFallback} />}
        </div>
        <div>
          <h1 className={styles.storeName}>{storeName}</h1>
          <div className={styles.meta}>
            <span className={styles.dot} />
            <span>{isOpen ? "Aberto" : "Fechado"}</span>
            <span>• {deliveryTime}</span>
            <span>• @{slug}</span>
          </div>
        </div>
      </div>
    </header>
  );
}

function MenuInfoBar({ deliveryTime, deliveryFee, paymentMethods }: { deliveryTime: string; deliveryFee: string; paymentMethods: string }) {
  return (
    <section className={styles.infoBar}>
      <div className={styles.chip}><span className={styles.chipHead}><ClockIcon />Entrega</span><strong>{deliveryTime}</strong></div>
      <div className={styles.chip}><span className={styles.chipHead}><PinIcon />Taxa</span><strong>{deliveryFee}</strong></div>
      <div className={styles.chip}><span className={styles.chipHead}><CardIcon />Pagamento</span><strong>{paymentMethods}</strong></div>
    </section>
  );
}

function MenuSearch({ onSearch, searchQuery }: { onSearch: (query: string) => void; searchQuery: string }) {
  return (
    <div className={styles.searchWrap}>
      <div className={styles.searchBox}>
        <SearchIcon className={styles.searchIcon} />
        <input className={styles.search} value={searchQuery} onChange={(event) => onSearch(event.target.value)} placeholder="Buscar no cardápio" />
      </div>
    </div>
  );
}

function MenuHighlights({ items, onAdd }: { items: PublicMenuItem[]; onAdd: (item: PublicMenuItem) => void }) {
  return (
    <section className={styles.sectionPad}>
      <p className={styles.label}>Destaques</p>
      <div className={styles.highlights}>
        {items.map((item) => {
          const badge = getItemBadge(item);
          return (
            <button key={item.id} type="button" className={`${styles.highlightCard} ${(item.featured || item.is_popular) ? styles.featured : ""}`} onClick={() => onAdd(item)}>
              <div style={{ height: 86, borderRadius: 10, overflow: "hidden" }}>{item.image_url ? <Image src={item.image_url} alt={item.name} width={132} height={86} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <PlaceholderIcon className={styles.imageFallback} />}</div>
              {badge ? <span className={`${styles.badge} ${badge.className}`}>{badge.label}</span> : null}
              <h3 className={styles.hName}>{item.name}</h3>
              <p className={styles.hPrice}>{formatCurrencyFromCents(item.price_cents)}</p>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function MenuCategoryNav({ categories, activeCategory, onSelect }: { categories: PublicMenuCategory[]; activeCategory: string; onSelect: (categoryId: string) => void }) {
  return (
    <nav className={styles.categoryNav}>
      {[{ id: "all", name: "Todos" }, ...categories.map((category) => ({ id: String(category.id), name: category.name }))].map((category) => (
        <button key={category.id} type="button" className={`${styles.pill} ${activeCategory === category.id ? styles.pillActive : ""}`} onClick={() => onSelect(category.id)}>{category.name}</button>
      ))}
    </nav>
  );
}

function MenuSections({ sections, onAdd, quantityByItem, popItemId }: { sections: PublicMenuCategory[]; onAdd: (item: PublicMenuItem) => void; quantityByItem: Record<number, number>; popItemId: number | null }) {
  return (
    <section className={styles.sectionPad}>
      {sections.map((section) => (
        <div key={section.id}>
          <h2 className={styles.sectionTitle}>{section.name}</h2>
          <p className={styles.sectionSubtitle}>{section.items.length} itens</p>
          {section.items.map((item) => (
            <MenuItemCard key={item.id} item={item} onAdd={onAdd} quantity={quantityByItem[item.id] ?? 0} pop={popItemId === item.id} />
          ))}
        </div>
      ))}
    </section>
  );
}

function MenuItemCard({ item, onAdd, quantity, pop }: { item: PublicMenuItem; onAdd: (item: PublicMenuItem) => void; quantity: number; pop: boolean }) {
  return (
    <article className={styles.itemCard} onClick={() => onAdd(item)} role="button">
      <div style={{ flex: 1 }}>
        <h3 className={styles.itemName}>{item.name}</h3>
        <p className={styles.itemDesc}>{item.description}</p>
        <div className={styles.itemFoot}>
          <span className={styles.itemPrice}>{formatCurrencyFromCents(item.price_cents)}</span>
          {(item.tags ?? []).slice(0, 2).map((tag) => <span key={tag} className={styles.tag}>{tag}</span>)}
        </div>
      </div>
      <div className={styles.itemMedia}>
        {item.image_url ? <Image src={item.image_url} alt={item.name} fill style={{ objectFit: "cover" }} /> : <PlaceholderIcon className={styles.imageFallback} />}
        <button type="button" className={`${styles.addBtn} ${pop ? styles.pop : ""}`} onClick={(event) => { event.stopPropagation(); onAdd(item); }}>
          +
          {quantity > 1 ? <span className={styles.qtyBadge}>{quantity}</span> : null}
        </button>
      </div>
    </article>
  );
}

function MenuCartBar({ itemCount, total, onClick }: { itemCount: number; total: number; onClick: () => void }) {
  return (
    <button type="button" className={styles.cartBar} onClick={onClick}>
      <div className={styles.cartLeft}>
        <span className={styles.cartCount}>{itemCount}</span>
        <span>Ver carrinho</span>
      </div>
      <span className={styles.cartTotal}>{formatCurrencyFromCents(total)}</span>
    </button>
  );
}

function MenuFooter() {
  return <footer className={styles.footer}>Powered by <span>Service Delivery</span></footer>;
}

function PlaceholderIcon({ className }: { className?: string }) {
  return (
    <div className={className}>
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M6 18c5 0 10-6 12-12-6 2-12 7-12 12Z" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.3" />
        <path d="M8 16c.6-2.7 2.3-5.3 5-7" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.3" />
      </svg>
    </div>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="1.5"/></svg>;
}
function ClockIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M12 8v5l3 2" stroke="currentColor" strokeWidth="1.5"/></svg>; }
function PinIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M12 21s6-5.8 6-10a6 6 0 1 0-12 0c0 4.2 6 10 6 10Z" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="11" r="2.5" stroke="currentColor" strokeWidth="1.5"/></svg>; }
function CardIcon() { return <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><rect x="3" y="6" width="18" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M3 10h18" stroke="currentColor" strokeWidth="1.5"/></svg>; }
function SunIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.5"/><path d="M12 2v2.5M12 19.5V22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2 12h2.5M19.5 12H22M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" stroke="currentColor" strokeWidth="1.5"/></svg>; }
function MoonIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M20 14.2A8 8 0 1 1 9.8 4a7 7 0 1 0 10.2 10.2Z" stroke="currentColor" strokeWidth="1.5"/></svg>; }
