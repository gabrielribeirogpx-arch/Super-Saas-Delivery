"use client";

import Image from "next/image";
import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";

import { CheckoutModal } from "@/components/CheckoutModal";
import { OrderSummary } from "@/components/storefront/OrderSummary";
import { getLatestCachedTrackingOrder, getOpenOrderSummary, setOpenOrderSummary, TRACKING_ORDER_UPDATED_EVENT, type CachedTrackingOrder } from "@/lib/orderTrackingCache";
import CustomerInstallPrompt from "@/components/pwa/CustomerInstallPrompt";
import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";
import { ItemDetailSheet } from "@/components/ItemDetailSheet";
import { CartItemWithModifiers, PublicMenuCategory, PublicMenuItem, PublicMenuResponse } from "@/components/storefront/types";
import { formatCurrencyFromCents } from "@/lib/currency";
import { hasOptionalCustomization, hasRequiredCustomization, shouldOpenCustomization } from "@/lib/productCustomization";
import {
  addConfiguredCartItem,
  clearStorefrontCart,
  getCartItemCount,
  getCartTotalInCents,
  getStorefrontCartKey,
  readStorefrontCart,
  writeStorefrontCart,
} from "@/lib/storefrontCart";

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
  if (item.featured || item.is_popular) return { label: "Destaque", className: styles.badgeAccent };
  if ((item.tags ?? []).some((tag) => tag.toLowerCase() === "especial")) return { label: "Especial", className: styles.badgeGreen };
  if ((item.tags ?? []).some((tag) => tag.toLowerCase() === "novo")) return { label: "Novo", className: styles.badgeCoral };
  return null;
};

export function PublicMenuPage({ menu, enableCart = true, forcedTheme, previewStyle, hideThemeToggle = false }: PublicMenuPageProps) {
  const merchantAccent = menu.public_settings?.primary_color;
  const premiumAccent = merchantAccent && /^#[0-9a-f]{6}$/i.test(merchantAccent) && merchantAccent.toLowerCase() !== "#dc2626" ? merchantAccent : "#f5a332";
  const rgb = [1, 3, 5].map(offset => parseInt(premiumAccent.slice(offset, offset + 2), 16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
  const premiumInk = .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2] > .179 ? "#17110a" : "#ffffff";
  const usesDefaultTemplate = menu.public_settings?.theme === "white" && menu.public_settings?.primary_color?.toLowerCase() === "#dc2626";
  const [theme, setTheme] = useState<ThemeMode>(forcedTheme ?? "dark");
  const [themeHydrated, setThemeHydrated] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("all");
  const [cartItems, setCartItems] = useState<CartItemWithModifiers[]>([]);
  const [hydratedCartStorageKey, setHydratedCartStorageKey] = useState<string | null>(null);
  const [popItemId, setPopItemId] = useState<number | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [recentOrder, setRecentOrder] = useState<CachedTrackingOrder | null>(null);
  const [summaryOrder, setSummaryOrder] = useState<CachedTrackingOrder | null>(null);

  useEffect(() => {
    if (!enableCart) return;
    setSummaryOrder(getOpenOrderSummary(menu.slug));
    const refreshRecent = () => setRecentOrder(getLatestCachedTrackingOrder(menu.slug));
    refreshRecent();
    window.addEventListener(TRACKING_ORDER_UPDATED_EVENT, refreshRecent);
    return () => window.removeEventListener(TRACKING_ORDER_UPDATED_EVENT, refreshRecent);
  }, [menu.slug, enableCart]);

  const [selectedItem, setSelectedItem] = useState<PublicMenuItem | null>(null);

  const cartStorageKey = useMemo(() => getStorefrontCartKey(menu.slug), [menu.slug]);

  useEffect(() => {
    if (forcedTheme) {
      setTheme(forcedTheme);
      return;
    }

    const storedTheme = typeof window !== "undefined" ? localStorage.getItem("menu-theme") : null;
    if (storedTheme === "dark" || storedTheme === "white") setTheme(storedTheme);
    setThemeHydrated(true);
  }, [forcedTheme]);

  useEffect(() => {
    if (forcedTheme || !themeHydrated) return;
    localStorage.setItem("menu-theme", theme);
  }, [forcedTheme, theme, themeHydrated]);

  useEffect(() => {
    try {
      setCartItems(readStorefrontCart<CartItemWithModifiers>(window.localStorage, menu.slug));
    } catch {
      // Ignora erro de parse para não quebrar o cardápio público.
    } finally {
      setHydratedCartStorageKey(cartStorageKey);
    }
  }, [cartStorageKey, menu.slug]);

  useEffect(() => {
    if (hydratedCartStorageKey !== cartStorageKey) return;
    writeStorefrontCart(window.localStorage, menu.slug, cartItems);
    window.dispatchEvent(new CustomEvent("storefront-cart-change"));
  }, [cartItems, cartStorageKey, hydratedCartStorageKey, menu.slug]);


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
    return allItems.filter((item) => item.is_active !== false && item.isAvailable !== false)
      .sort((a, b) => {
        const aScore = a.featured ? 100000 : a.orderCount ?? 0;
        const bScore = b.featured ? 100000 : b.orderCount ?? 0;
        return bScore - aScore;
      })
      .slice(0, 5);
  }, [allItems]);

  const cartIsHydrated = hydratedCartStorageKey === cartStorageKey;
  const quantityByItem = useMemo(
    () => cartIsHydrated ? cartItems.reduce<Record<number, number>>((acc, entry) => ({ ...acc, [entry.menuItemId]: acc[entry.menuItemId] ? acc[entry.menuItemId] + entry.quantity : entry.quantity }), {}) : {},
    [cartIsHydrated, cartItems],
  );

  const addToCart = (cartItem: CartItemWithModifiers) => {
    setCartItems((current) => addConfiguredCartItem(current, cartItem));
    setPopItemId(cartItem.menuItemId);
    window.setTimeout(() => setPopItemId(null), 220);
  };

  const addItemWithoutCustomization = (item: PublicMenuItem) => {
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
  };

  const handleItemClick = (item: PublicMenuItem) => {
    if (shouldOpenCustomization(item)) {
      setSelectedItem(item);
      return;
    }
    addItemWithoutCustomization(item);
  };

  const cartCount = cartIsHydrated ? getCartItemCount(cartItems) : 0;
  const cartTotal = cartIsHydrated ? getCartTotalInCents(cartItems) : 0;

  const hideDiscovery = searchQuery.trim().length > 0;

  useEffect(() => {
    const openCart = () => setCheckoutOpen(true);
    if (window.location.hash === "#cart") {
      openCart();
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    }
    window.addEventListener("storefront-open-cart", openCart);
    return () => window.removeEventListener("storefront-open-cart", openCart);
  }, []);

  return (
    <main className={`${styles.page} ${styles.premium} ${usesDefaultTemplate ? styles.defaultTemplate : ""}`} data-theme={theme} data-cart-bar-visible={enableCart && cartCount > 0 ? "true" : "false"} style={{ "--premium-accent": premiumAccent, "--premium-ink": premiumInk, ...previewStyle } as CSSProperties}>
      <div className={styles.container}>
        {enableCart && recentOrder && <button
          type="button"
          className="my-3 w-full rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-center text-sm font-semibold text-emerald-800"
          onClick={() => {
            setOpenOrderSummary(menu.slug, recentOrder.token);
            setSummaryOrder(recentOrder);
          }}
        >Acompanhar pedido{recentOrder.orderNumber ? ` #${recentOrder.orderNumber}` : ""}</button>}
        {enableCart && summaryOrder && <div className={styles.summaryOverlay}>
          <div className="mx-auto max-w-xl">
            <OrderSummary order={summaryOrder} onBack={() => {
              setOpenOrderSummary(menu.slug, null);
              setSummaryOrder(null);
            }} />
          </div>
        </div>}

        <MenuHero
          coverUrl={menu.public_settings?.cover_image_url}
          avatarUrl={menu.public_settings?.logo_url}
          storeName={menu.tenant.name}
          slug={menu.slug}
          refinedFallback={usesDefaultTemplate}
          isOpen={Boolean(menu.tenant.is_open ?? menu.tenant.manual_open_status ?? true)}
          deliveryTime={menu.tenant.estimated_prep_time ?? "25-40 min"}
          theme={theme}
          onToggleTheme={() => setTheme((current) => (current === "white" ? "dark" : "white"))}
          hideThemeToggle={hideThemeToggle || Boolean(forcedTheme)}
        />

        <MenuInfoBar
          deliveryTime={menu.tenant.estimated_prep_time ?? "25-40 min"}
          deliveryFee={formatCurrencyFromCents(Math.round(Number(menu.tenant.delivery_fee ?? 0) * 100))}
          paymentMethods="Pix, Cartão"
        />

        <MenuSearch onSearch={(query) => { setSearchQuery(query); setActiveCategory("all"); }} searchQuery={searchQuery} />

        {enableCart && <MenuInstallSection storeName={menu.tenant.name} />}

        {!hideDiscovery && activeCategory === "all" && highlightedItems.length > 0 && <MenuHighlights items={highlightedItems} onAdd={setSelectedItem} />}

        {!hideDiscovery && (
          <MenuCategoryNav
            categories={normalizedSections}
            activeCategory={activeCategory}
            onSelect={(id) => setActiveCategory(id)}
          />
        )}

        <MenuSections sections={filteredSections} onAdd={handleItemClick} onCustomize={setSelectedItem} quantityByItem={quantityByItem} popItemId={popItemId} />

        {filteredSections.length === 0 && <div className={styles.empty} role="status">
          <SearchIcon />
          <h2>Nenhum item encontrado</h2>
          <p>{searchQuery.trim() ? "Tente outro nome ou explore o cardápio completo." : "Os produtos disponíveis aparecerão aqui."}</p>
          {(searchQuery.trim() || activeCategory !== "all") && <button type="button" className={styles.resetSearch} onClick={() => { setSearchQuery(""); setActiveCategory("all"); }}>Ver todo o cardápio</button>}
        </div>}

        {enableCart && cartCount > 0 && <MenuCartBar itemCount={cartCount} total={cartTotal} onClick={() => setCheckoutOpen(true)} />}


        <CheckoutModal
          recommendations={[...menu.categories.flatMap(category => category.items), ...(menu.items_without_category ?? [])].filter(item => item.is_active !== false && item.isAvailable !== false && !(item.modifier_groups ?? []).some(group => group.required || group.min_selection > 0))}
          productImages={Object.fromEntries([...menu.categories.flatMap(category => category.items), ...(menu.items_without_category ?? [])].filter(item => item.image_url).map(item => [item.id, item.image_url as string]))}
          isOpen={checkoutOpen}
          onClose={() => setCheckoutOpen(false)}
          cartItems={cartIsHydrated ? cartItems : []}
          onCartChange={(items) => setCartItems(items as CartItemWithModifiers[])}
          onOrderSuccess={() => {
            setCartItems([]);
            clearStorefrontCart(localStorage, menu.slug);
            setCheckoutOpen(false);
          }}
          tenant={{ slug: menu.slug, store_id: menu.tenant_id, name: menu.tenant.name, delivery_fee: Number(menu.tenant.delivery_fee ?? 0) }}
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

        <CustomerInstallPrompt storeName={menu.tenant.name} />
        <CustomerBottomNav slug={menu.slug} />
        <MenuFooter />
      </div>
    </main>
  );
}

function MenuInstallSection({ storeName }: { storeName: string }) {
  return (
    <section className={styles.installSection}>
      <div>
        <p className={styles.installTitle}>Tenha a {storeName} no seu celular</p>
        <p className={styles.installText}>Faça pedidos e acompanhe entregas com mais facilidade.</p>
      </div>
      <button type="button" className={styles.installButton} onClick={() => window.dispatchEvent(new CustomEvent("customer-pwa-install-click"))}>Instalar aplicativo</button>
    </section>
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
  refinedFallback,
}: {
  refinedFallback?: boolean;
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
    <header className={styles.hero} data-has-cover={Boolean(coverUrl)}>
      {coverUrl ? <Image src={coverUrl} alt={storeName} fill style={{ objectFit: "cover" }} /> : <PlaceholderIcon className={styles.heroFallback} />}
      <div className={styles.heroOverlay} />
      <div className={styles.heroActions}>
        {hideThemeToggle ? null : <MenuThemeToggle onToggle={onToggleTheme} theme={theme} />}
        <button type="button" className={styles.shareButton} aria-label="Compartilhar cardápio" onClick={async () => {
          const url = window.location.href;
          if (navigator.share) { try { await navigator.share({ title: storeName, url }); } catch { /* Share sheet dismissed. */ } }
          else { try { await navigator.clipboard.writeText(url); } catch { /* Clipboard unavailable. */ } }
        }}><ShareIcon /></button>
      </div>
      <div className={styles.heroContent}>
        <div className={styles.avatar}>
          {avatarUrl ? <Image src={avatarUrl} alt={`Logo ${storeName}`} width={58} height={58} /> : refinedFallback ? <span className={styles.logoFallback} aria-label={`Logo ${storeName}`}>{storeName.trim().split(/\s+/).slice(0, 2).map((word) => Array.from(word)[0]).join("").toUpperCase() || "F"}</span> : <PlaceholderIcon className={styles.imageFallback} />}
        </div>
        <div className={styles.heroInfo}>
          <h1 className={styles.storeName}>{storeName}</h1>
          <div className={styles.meta}>
            <span className={styles.storeStatus}><span className={`${styles.dot} ${isOpen ? "" : styles.closedDot}`} />{isOpen ? "Aberto agora" : "Fechado"}</span>
            <span>• {deliveryTime}</span>
            <span className={styles.storeSlug}>@{slug}</span>
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
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className={styles.searchWrap}>
      <div className={styles.searchBox}>
        <SearchIcon className={styles.searchIcon} />
        <input ref={inputRef} type="search" enterKeyHint="search" className={styles.search} value={searchQuery} onChange={(event) => onSearch(event.target.value)} aria-label="Buscar no cardápio" placeholder="O que você quer pedir hoje?" />
        {searchQuery && <button type="button" className={styles.clearSearch} aria-label="Limpar busca" onClick={() => { onSearch(""); inputRef.current?.focus(); }}>×</button>}
      </div>
    </div>
  );
}

function MenuHighlights({ items, onAdd }: { items: PublicMenuItem[]; onAdd: (item: PublicMenuItem) => void }) {
  return (
    <section className={styles.sectionPad}>
      <div className={styles.sectionHeading}><div><h2 className={styles.label}>Para dar água na boca</h2></div><span className={styles.swipeHint}>Deslize para ver →</span></div>
      <div className={styles.highlights}>
        {items.map((item) => {
          const badge = getItemBadge(item);
          return (
            <button key={item.id} type="button" className={`${styles.highlightCard} ${(item.featured || item.is_popular) ? styles.featured : ""}`} onClick={() => onAdd(item)}>
              <div className={styles.highlightMedia}>{item.image_url ? <Image src={item.image_url} alt={item.name} width={132} height={86} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <PlaceholderIcon className={styles.imageFallback} />}</div>
              {badge ? <span className={`${styles.badge} ${badge.className}`}>{badge.label}</span> : null}
              <h3 className={styles.hName}>{item.name}</h3><p className={styles.hDescription}>{item.description}</p>
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
    <nav className={styles.categoryNav} aria-label="Categorias do cardápio">
      {[{ id: "all", name: "Todos" }, ...categories.map((category) => ({ id: String(category.id), name: category.name }))].map((category) => (
        <button key={category.id} type="button" className={`${styles.pill} ${activeCategory === category.id ? styles.pillActive : ""}`} aria-current={activeCategory === category.id ? "true" : undefined} onClick={() => onSelect(category.id)}>{category.name}</button>
      ))}
    </nav>
  );
}

function MenuSections({ sections, onAdd, onCustomize, quantityByItem, popItemId }: { sections: PublicMenuCategory[]; onAdd: (item: PublicMenuItem) => void; onCustomize: (item: PublicMenuItem) => void; quantityByItem: Record<number, number>; popItemId: number | null }) {
  return (
    <section className={styles.sectionPad}>
      {sections.map((section) => (
        <div key={section.id}>
          <div className={styles.categoryHeading}><h2 className={styles.sectionTitle}>{section.name === "Sem categoria" ? "Nosso cardápio" : section.name}</h2>
          <span className={styles.sectionSubtitle}>{section.items.length} {section.items.length === 1 ? "item" : "itens"}</span></div>
          <div className={styles.itemGrid}>{section.items.map((item) => (
            <MenuItemCard key={item.id} item={item} onAdd={onAdd} onCustomize={onCustomize} quantity={quantityByItem[item.id] ?? 0} pop={popItemId === item.id} />
          ))}</div>
        </div>
      ))}
    </section>
  );
}

function MenuItemCard({ item, onAdd, onCustomize, quantity, pop }: { item: PublicMenuItem; onAdd: (item: PublicMenuItem) => void; onCustomize: (item: PublicMenuItem) => void; quantity: number; pop: boolean }) {
  const canCustomize = hasOptionalCustomization(item) && !hasRequiredCustomization(item);
  return (
    <article className={styles.itemCard} onClick={() => onCustomize(item)} role="button" tabIndex={0} onKeyDown={(event) => { if (event.target !== event.currentTarget) return; if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onCustomize(item); } }}>
      <div className={styles.itemInfo}>
        <h3 className={styles.itemName}>{item.name}</h3>
        <p className={styles.itemDesc}>{item.description}</p>
        <div className={styles.itemFoot}>
          <span className={styles.itemPrice}>{formatCurrencyFromCents(item.price_cents)}</span>
          {(item.tags ?? []).slice(0, 2).map((tag) => <span key={tag} className={styles.tag}>{tag}</span>)}
          {canCustomize ? <button type="button" className={styles.customizeButton} onClick={(event) => { event.stopPropagation(); onCustomize(item); }}>Personalizar</button> : null}
        </div>
      </div>
      <div className={styles.itemMedia}>
        {item.image_url ? <Image src={item.image_url} alt={item.name} fill style={{ objectFit: "cover" }} /> : <PlaceholderIcon className={styles.imageFallback} />}
        <button type="button" aria-label={`Adicionar ${item.name}`} className={`${styles.addBtn} ${pop ? styles.pop : ""}`} onClick={(event) => { event.stopPropagation(); onAdd(item); }}>
          +
          {quantity > 0 ? <span className={styles.qtyBadge}>{quantity}</span> : null}
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
  return <footer className={styles.footer}>Powered by <span>Fomizero</span></footer>;
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
function ShareIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 16V3m-4 4 4-4 4 4M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" /></svg>; }
function SunIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.5"/><path d="M12 2v2.5M12 19.5V22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2 12h2.5M19.5 12H22M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" stroke="currentColor" strokeWidth="1.5"/></svg>; }
function MoonIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M20 14.2A8 8 0 1 1 9.8 4a7 7 0 1 0 10.2 10.2Z" stroke="currentColor" strokeWidth="1.5"/></svg>; }
