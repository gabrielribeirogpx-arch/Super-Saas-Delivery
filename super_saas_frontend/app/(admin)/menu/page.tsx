"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ImagePlus, Pencil, Plus, Trash2, UtensilsCrossed, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useSession } from "@/hooks/use-session";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { LoadingExperience, LoadingLine } from "@/components/ui/loading-experience";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/media";
import { parseMenuPriceCents } from "@/lib/menuProductForm";

interface MenuCategory {
  id: number;
  tenant_id: number;
  name: string;
  sort_order: number;
  active: boolean;
}

interface MenuItem {
  id: number;
  tenant_id: number;
  category_id: number | null;
  name: string;
  description?: string | null;
  price_cents: number;
  image_url?: string | null;
  active: boolean;
  modifier_groups?: ModifierGroup[];
}

interface ModifierGroup {
  id: number;
  name: string;
  required: boolean;
  min_selection: number;
  max_selection: number;
  options: ModifierOption[];
}

interface ModifierOption {
  id: number;
  name: string;
  price_delta: string | number;
  is_active: boolean;
}

interface MenuItemFormState {
  name: string;
  description: string;
  price: string;
  categoryId: string;
  active: boolean;
  imageFile: File | null;
}

interface ConfirmDialogState {
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => Promise<void> | void;
}

const emptyItemState: MenuItemFormState = {
  name: "",
  description: "",
  price: "",
  categoryId: "",
  active: true,
  imageFile: null,
};

const itemFormSnapshot = (form: MenuItemFormState) => JSON.stringify({
  name: form.name, description: form.description, price: form.price,
  categoryId: form.categoryId, active: form.active,
});
const categoryFormSnapshot = (name: string, order: string, active: boolean) => JSON.stringify({ name, order, active });

function MenuItemCard({ item, onEdit, onDelete }: { item: MenuItem; onEdit: (item: MenuItem) => void; onDelete: (item: MenuItem) => void }) {
  const image = resolveMediaUrl(item.image_url);
  return (
    <article aria-label={item.name} className="flex min-w-0 flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-3 lg:flex-row lg:items-center lg:justify-between lg:gap-4">
      <div className="flex min-w-0 flex-1 items-start gap-3 lg:items-center">
        <div className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-100 bg-slate-50 sm:h-20 sm:w-20 lg:h-12 lg:w-12">
          <UtensilsCrossed aria-hidden="true" className="h-6 w-6 text-slate-300" />
          {image && <img key={image} src={image} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover" onError={event => { event.currentTarget.style.display = "none"; }} />}
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="break-words text-sm font-semibold leading-5 text-slate-950">{item.name}</h4>
          {item.description && <p className="mt-1 break-words text-xs leading-5 text-slate-500">{item.description}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
            <p className="whitespace-nowrap text-sm font-bold text-slate-900">{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(item.price_cents / 100)}</p>
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold ${item.active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}><span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${item.active ? "bg-emerald-500" : "bg-slate-400"}`} />{item.active ? "Ativo" : "Inativo"}</span>
          </div>
        </div>
      </div>
      <div className="grid shrink-0 grid-cols-2 gap-2 border-t border-slate-100 pt-3 lg:flex lg:border-0 lg:pt-0">
        <Button type="button" variant="outline" size="sm" aria-label={`Editar ${item.name}`} onClick={() => onEdit(item)} className="gap-2 border-brand-200 text-brand-700 hover:bg-brand-50"><Pencil aria-hidden="true" className="h-3.5 w-3.5" />Editar</Button>
        <Button type="button" variant="ghost" size="sm" aria-label={`Excluir ${item.name}`} onClick={() => onDelete(item)} className="gap-2 text-red-600 hover:bg-red-50 hover:text-red-700"><Trash2 aria-hidden="true" className="h-3.5 w-3.5" />Excluir</Button>
      </div>
    </article>
  );
}

export default function MenuPage() {
  const queryClient = useQueryClient();
  const { data: session, isLoading: isSessionLoading } = useSession();
  const tenantId = session?.tenant_id;
  const [editingCategory, setEditingCategory] = useState<MenuCategory | null>(null);
  const [categoryName, setCategoryName] = useState("");
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [categoryOrder, setCategoryOrder] = useState("0");
  const [categoryActive, setCategoryActive] = useState(true);
  const categoryEditorRef = useRef<HTMLDivElement>(null);
  const mobileCategoryCloseRef = useRef<HTMLButtonElement>(null);
  const categoryDraftBaselineRef = useRef(categoryFormSnapshot("", "0", true));
  const [isMobileCategoryEditorOpen, setIsMobileCategoryEditorOpen] = useState(false);
  const [categoryOrderError, setCategoryOrderError] = useState<string | null>(null);
  const itemEditorRef = useRef<HTMLDivElement>(null);
  const mobileEditorCloseRef = useRef<HTMLButtonElement>(null);
  const itemDraftBaselineRef = useRef(itemFormSnapshot(emptyItemState));
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [itemForm, setItemForm] = useState<MenuItemFormState>(emptyItemState);
  const [isMobileItemEditorOpen, setIsMobileItemEditorOpen] = useState(false);
  const [itemFormErrors, setItemFormErrors] = useState<{ name?: string; price?: string }>({});
  const [itemSaveError, setItemSaveError] = useState<string | null>(null);
  const [itemSuccess, setItemSuccess] = useState<string | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [isModifiersModalOpen, setIsModifiersModalOpen] = useState(false);
  const [modifiersProduct, setModifiersProduct] = useState<MenuItem | null>(null);
  const [isLoadingModifiers, setIsLoadingModifiers] = useState(false);
  const [modifiersError, setModifiersError] = useState<string | null>(null);
  const [modifiersSuccess, setModifiersSuccess] = useState<string | null>(null);
  const [isCreateGroupFormOpen, setIsCreateGroupFormOpen] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [groupName, setGroupName] = useState("");
  const [groupRequired, setGroupRequired] = useState(false);
  const [groupMinSelection, setGroupMinSelection] = useState("0");
  const [groupMaxSelection, setGroupMaxSelection] = useState("1");
  const [savingGroup, setSavingGroup] = useState(false);
  const [savingGroupChanges, setSavingGroupChanges] = useState(false);
  const [optionName, setOptionName] = useState("");
  const [optionPriceDelta, setOptionPriceDelta] = useState("0");
  const [optionActive, setOptionActive] = useState(true);
  const [savingOption, setSavingOption] = useState(false);
  const [isDeletingModifier, setIsDeletingModifier] = useState(false);
  const [deletingGroupId, setDeletingGroupId] = useState<number | null>(null);
  const [deletingOptionId, setDeletingOptionId] = useState<number | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [deleteErrorToast, setDeleteErrorToast] = useState<string | null>(null);
  const deleteErrorToastTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ["menu-categories", tenantId],
    queryFn: () => api.get<MenuCategory[]>(`/api/admin/menu/categories`),
    enabled: Boolean(tenantId),
  });

  const itemsQuery = useQuery({
    queryKey: ["menu-items", tenantId],
    queryFn: () => api.get<MenuItem[]>(`/api/admin/menu/items`),
    enabled: Boolean(tenantId),
  });

  const createCategory = useMutation({
    mutationFn: (payload: { tenant_id: number; name: string; sort_order: number; active: boolean }) =>
      api.post<MenuCategory>("/api/admin/menu/categories", {
        ...payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-categories"] });
      setCategoryName("");
      setCategoryOrder("0");
      setCategoryActive(true);
      setCategoryError(null);
      setCategoryOrderError(null);
      setIsMobileCategoryEditorOpen(false);
      setItemSuccess("Categoria criada. Agora você pode adicionar produtos nela.");
    },
    onError: () => setCategoryError("Não foi possível criar a categoria. Tente novamente."),
  });

  const updateCategory = useMutation({
    mutationFn: (payload: { id: number; name: string; sort_order: number; active: boolean }) =>
      api.put<MenuCategory>(
        `/api/admin/menu/categories/${payload.id}`,
        {
          name: payload.name,
          sort_order: payload.sort_order,
          active: payload.active,
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-categories"] });
      setEditingCategory(null);
      setCategoryName("");
      setCategoryOrder("0");
      setCategoryActive(true);
      setCategoryError(null);
      setCategoryOrderError(null);
      setIsMobileCategoryEditorOpen(false);
      setItemSuccess("Categoria atualizada.");
    },
    onError: () => setCategoryError("Não foi possível salvar a categoria. Tente novamente."),
  });

  const deactivateCategory = useMutation({
    mutationFn: (categoryId: number) =>
      api.delete<MenuCategory>(
        `/api/admin/menu/categories/${categoryId}`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-categories"] });
    },
  });

  const createItem = useMutation({
    mutationFn: (formData: FormData) =>
      api.post<MenuItem>("/api/admin/menu/items", formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
      setItemForm(emptyItemState);
      setIsMobileItemEditorOpen(false);
      setItemSaveError(null);
      setItemSuccess("Produto cadastrado no cardápio.");
    },
    onError: () => setItemSaveError("Não foi possível cadastrar o produto. Confira os dados e tente novamente."),
  });

  const updateItem = useMutation({
    mutationFn: (payload: { id: number; formData: FormData }) =>
      api.put<MenuItem>(`/api/admin/menu/items/${payload.id}`, payload.formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
      setEditingItem(null);
      setItemForm(emptyItemState);
      setIsMobileItemEditorOpen(false);
      setItemSaveError(null);
      setItemSuccess("Produto atualizado com sucesso.");
    },
    onError: () => setItemSaveError("Não foi possível salvar o produto. Tente novamente."),
  });

  const deactivateItem = useMutation({
    mutationFn: (itemId: number) =>
      api.delete<MenuItem>(`/api/admin/menu/items/${itemId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
    },
  });


  const showDeleteErrorToast = (message: string) => {
    if (deleteErrorToastTimeoutRef.current) {
      clearTimeout(deleteErrorToastTimeoutRef.current);
    }

    setDeleteErrorToast(message);
    deleteErrorToastTimeoutRef.current = setTimeout(() => {
      setDeleteErrorToast(null);
      deleteErrorToastTimeoutRef.current = null;
    }, 3000);
  };

  const categories = categoriesQuery.data ?? [];
  const items = itemsQuery.data ?? [];
  const itemsByCategory = useMemo(() => {
    const grouped = new Map<string, MenuItem[]>();
    items.forEach((item) => {
      const key = item.category_id ? String(item.category_id) : "uncategorized";
      const bucket = grouped.get(key) ?? [];
      bucket.push(item);
      grouped.set(key, bucket);
    });
    return grouped;
  }, [items]);

  const handleCategorySubmit = () => {
    if (!tenantId) {
      return;
    }

    if (!categoryName.trim()) {
      setCategoryError("Informe o nome da categoria.");
      return;
    }
    const order = Number(categoryOrder);
    if (!Number.isInteger(order) || order < 0) {
      setCategoryOrderError("Informe uma ordem válida a partir de 0.");
      return;
    }
    setCategoryError(null);
    setCategoryOrderError(null);
    const categoryPayload = {
      name: categoryName.trim(),
      sort_order: order,
      active: categoryActive,
    };
    if (editingCategory) {
      updateCategory.mutate({ id: editingCategory.id, ...categoryPayload });
    } else {
      createCategory.mutate({ tenant_id: tenantId, ...categoryPayload });
    }
  };

  const startNewCategory = () => {
    const nextOrder = String(categories.reduce((highest, category) => Math.max(highest, category.sort_order), -1) + 1);
    setEditingCategory(null);
    setCategoryName("");
    setCategoryOrder(nextOrder);
    setCategoryActive(true);
    categoryDraftBaselineRef.current = categoryFormSnapshot("", nextOrder, true);
    setCategoryError(null);
    setCategoryOrderError(null);
    setItemSuccess(null);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      setIsMobileCategoryEditorOpen(true);
    } else {
      window.requestAnimationFrame(() => categoryEditorRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    }
  };

  const handleEditCategory = (category: MenuCategory) => {
    setEditingCategory(category);
    setCategoryName(category.name);
    setCategoryOrder(String(category.sort_order));
    setCategoryActive(category.active);
    categoryDraftBaselineRef.current = categoryFormSnapshot(category.name, String(category.sort_order), category.active);
    setCategoryError(null);
    setCategoryOrderError(null);
    setItemSuccess(null);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      setIsMobileCategoryEditorOpen(true);
    } else {
      window.requestAnimationFrame(() => categoryEditorRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    }
  };

  const categorySaving = createCategory.isPending || updateCategory.isPending;
  const closeCategoryEditor = () => {
    if (categorySaving) return;
    if (categoryFormSnapshot(categoryName, categoryOrder, categoryActive) !== categoryDraftBaselineRef.current && !window.confirm("Descartar alterações desta categoria?")) return;
    setIsMobileCategoryEditorOpen(false);
    setEditingCategory(null);
    setCategoryName("");
    setCategoryOrder("0");
    setCategoryActive(true);
    setCategoryError(null);
    setCategoryOrderError(null);
  };

  const handleDeleteCategory = (category: MenuCategory) => {
    setConfirmDialog({
      title: "Excluir categoria",
      description: `Deseja realmente excluir a categoria "${category.name}"?`,
      onConfirm: async () => {
        await deactivateCategory.mutateAsync(category.id);
      },
    });
  };

  const handleItemSubmit = () => {
    if (!tenantId) {
      return;
    }

    const name = itemForm.name.trim();
    const priceCents = parseMenuPriceCents(itemForm.price);
    const errors = {
      name: name ? undefined : "Informe o nome do produto.",
      price: priceCents === null ? "Informe um preço válido, por exemplo 29,90." : undefined,
    };
    setItemFormErrors(errors);
    setItemSaveError(null);
    if (errors.name || errors.price || priceCents === null) return;

    const formData = new FormData();
    formData.append("name", name);
    formData.append("tenant_id", String(tenantId));
    formData.append("description", itemForm.description.trim());
    formData.append("price_cents", String(priceCents));
    if (editingItem) {
      formData.append("category_id", itemForm.categoryId || "-1");
    } else if (itemForm.categoryId) {
      formData.append("category_id", itemForm.categoryId);
    }
    formData.append("active", String(itemForm.active));
    if (itemForm.imageFile) {
      formData.append("image", itemForm.imageFile);
    }

    if (editingItem) {
      updateItem.mutate({ id: editingItem.id, formData });
    } else {
      createItem.mutate(formData);
    }
  };

  const startNewItem = (categoryId = "") => {
    setEditingItem(null);
    const nextForm = { ...emptyItemState, categoryId };
    setItemForm(nextForm);
    itemDraftBaselineRef.current = itemFormSnapshot(nextForm);
    setItemFormErrors({});
    setItemSaveError(null);
    setItemSuccess(null);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      setIsMobileItemEditorOpen(true);
    } else {
      window.requestAnimationFrame(() => itemEditorRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    }
  };

  const handleEditItem = (item: MenuItem) => {
    setEditingItem(item);
    const nextForm = {
      name: item.name,
      description: item.description ?? "",
      price: (item.price_cents / 100).toFixed(2),
      categoryId: item.category_id ? String(item.category_id) : "",
      active: item.active,
      imageFile: null,
    };
    setItemForm(nextForm);
    itemDraftBaselineRef.current = itemFormSnapshot(nextForm);
    setItemFormErrors({});
    setItemSaveError(null);
    setItemSuccess(null);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      setIsMobileItemEditorOpen(true);
    } else {
      window.requestAnimationFrame(() => itemEditorRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    }
  };

  const handleDeleteItem = (item: MenuItem) => {
    setConfirmDialog({
      title: "Excluir item",
      description: `Deseja realmente excluir o item "${item.name}"?`,
      onConfirm: async () => {
        try {
          await deactivateItem.mutateAsync(item.id);
        } catch {
          showDeleteErrorToast("Erro ao excluir item");
          throw new Error("Erro ao excluir item");
        }
      },
    });
  };

  const loadProductModifiers = async (productId: number) => {
    setIsLoadingModifiers(true);
    setModifiersError(null);
    try {
      const products = await api.get<MenuItem[]>("/api/admin/menu/items");
      const product = products.find((entry) => entry.id === productId);
      if (!product) {
        setModifiersError("Produto não encontrado.");
        setModifiersProduct(null);
        return null;
      }
      setModifiersProduct(product);
      setSelectedGroupId((current) => {
        if (current && (product.modifier_groups ?? []).some((group) => group.id === current)) {
          return current;
        }
        return product.modifier_groups?.[0]?.id ?? null;
      });
      return product;
    } catch {
      setModifiersError("Não foi possível carregar adicionais deste produto.");
      setModifiersProduct(null);
      return null;
    } finally {
      setIsLoadingModifiers(false);
    }
  };

  const handleOpenModifiersModal = async () => {
    if (!editingItem) {
      return;
    }
    setIsModifiersModalOpen(true);
    setIsCreateGroupFormOpen(false);
    setSelectedGroupId(null);
    await loadProductModifiers(editingItem.id);
  };

  const resetCreateGroupForm = () => {
    setGroupName("");
    setGroupRequired(false);
    setGroupMinSelection("0");
    setGroupMaxSelection("1");
  };

  const handleCreateGroup = async () => {
    if (!modifiersProduct || !groupName.trim()) {
      return;
    }
    setSavingGroup(true);
    setModifiersError(null);
    setModifiersSuccess(null);
    try {
      await api.post(`/api/admin/products/${modifiersProduct.id}/modifier-groups`, {
        name: groupName.trim(),
        required: groupRequired,
        min_selection: Number(groupMinSelection || 0),
        max_selection: Number(groupMaxSelection || 0),
      });
      resetCreateGroupForm();
      setIsCreateGroupFormOpen(false);
      const refreshedProduct = await loadProductModifiers(modifiersProduct.id);
      const refreshedGroups = refreshedProduct?.modifier_groups ?? [];
      const latestGroup = refreshedGroups[refreshedGroups.length - 1];
      setSelectedGroupId(latestGroup?.id ?? null);
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
    } catch {
      setModifiersError("Não foi possível criar grupo.");
    } finally {
      setSavingGroup(false);
    }
  };

  const resetCreateOptionForm = () => {
    setOptionName("");
    setOptionPriceDelta("0");
    setOptionActive(true);
  };

  const handleCreateOption = async (groupId: number) => {
    if (!optionName.trim() || !modifiersProduct) {
      return;
    }
    setSavingOption(true);
    setModifiersError(null);
    setModifiersSuccess(null);
    try {
      await api.post(`/api/admin/modifier-groups/${groupId}/options`, {
        name: optionName.trim(),
        price_delta: Number(optionPriceDelta.replace(",", ".") || 0),
        is_active: optionActive,
      });
      resetCreateOptionForm();
      await loadProductModifiers(modifiersProduct.id);
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
    } catch {
      setModifiersError("Não foi possível criar opção.");
    } finally {
      setSavingOption(false);
    }
  };

  const deleteModifierEntity = async (
    type: "group" | "option",
    id: number,
    name: string
  ) => {
    if (!modifiersProduct || !tenantId) {
      return;
    }

    setIsDeletingModifier(true);
    setModifiersError(null);
    setModifiersSuccess(null);
    try {
      if (type === "group") {
        await api.delete(`/api/admin/modifier-groups/${id}`);
      } else {
        await api.delete(`/api/admin/modifier-options/${id}`);
      }

      const refreshedProduct = await loadProductModifiers(modifiersProduct.id);
      if (type === "group" && selectedGroupId === id) {
        const firstGroupId = refreshedProduct?.modifier_groups?.[0]?.id ?? null;
        setSelectedGroupId(firstGroupId);
      }

      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
      setModifiersSuccess(
        type === "group"
          ? `Grupo "${name}" excluído com sucesso.`
          : `Opção "${name}" excluída com sucesso.`
      );
    } catch {
      setModifiersError("Não foi possível excluir. Tente novamente.");
    } finally {
      setIsDeletingModifier(false);
      setDeletingGroupId(null);
      setDeletingOptionId(null);
    }
  };

  const handleDeleteGroup = (groupId: number, groupName: string) => {
    setConfirmDialog({
      title: "Excluir grupo",
      description: `Deseja excluir o grupo "${groupName}" e desativar suas opções?`,
      onConfirm: async () => {
        setDeletingGroupId(groupId);
        await deleteModifierEntity("group", groupId, groupName);
      },
    });
  };

  const handleDeleteOption = (optionId: number, optionName: string) => {
    setConfirmDialog({
      title: "Excluir opção",
      description: `Deseja excluir a opção "${optionName}"?`,
      onConfirm: async () => {
        setDeletingOptionId(optionId);
        await deleteModifierEntity("option", optionId, optionName);
      },
    });
  };

  const closeConfirmDialog = () => {
    if (isConfirmingDelete) {
      return;
    }
    setConfirmDialog(null);
  };

  const handleConfirmDelete = async () => {
    if (!confirmDialog) {
      return;
    }

    setIsConfirmingDelete(true);
    try {
      await confirmDialog.onConfirm();
      setConfirmDialog(null);
    } finally {
      setIsConfirmingDelete(false);
    }
  };

  const modifierGroups = modifiersProduct?.modifier_groups ?? [];
  const selectedGroup = modifierGroups.find((group) => group.id === selectedGroupId) ?? null;
  const activeOptions = selectedGroup?.options.filter((option) => option.is_active) ?? [];

  useEffect(() => {
    return () => {
      if (deleteErrorToastTimeoutRef.current) {
        clearTimeout(deleteErrorToastTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!selectedGroup) {
      return;
    }
    setGroupName(selectedGroup.name);
    setGroupRequired(selectedGroup.required);
    setGroupMinSelection(String(selectedGroup.min_selection));
    setGroupMaxSelection(String(selectedGroup.max_selection));
  }, [selectedGroup]);

  const handleSelectGroup = (group: ModifierGroup) => {
    setSelectedGroupId(group.id);
    setGroupName(group.name);
    setGroupRequired(group.required);
    setGroupMinSelection(String(group.min_selection));
    setGroupMaxSelection(String(group.max_selection));
    resetCreateOptionForm();
    setIsCreateGroupFormOpen(false);
  };

  const handleSaveSelectedGroup = async () => {
    if (!selectedGroup || !groupName.trim() || !modifiersProduct) {
      return;
    }

    setSavingGroupChanges(true);
    setModifiersError(null);
    setModifiersSuccess(null);
    try {
      await api.patch(`/api/admin/modifier-groups/${selectedGroup.id}`, {
        name: groupName.trim(),
        required: groupRequired,
        min_selection: Number(groupMinSelection || 0),
        max_selection: Number(groupMaxSelection || 0),
      });
      await loadProductModifiers(modifiersProduct.id);
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
    } catch {
      setModifiersError("Não foi possível salvar grupo.");
    } finally {
      setSavingGroupChanges(false);
    }
  };

  const itemSaving = createItem.isPending || updateItem.isPending;
  const closeItemEditor = () => {
    if (itemSaving) return;
    if ((itemFormSnapshot(itemForm) !== itemDraftBaselineRef.current || itemForm.imageFile) && !window.confirm("Descartar alterações deste produto?")) return;
    setIsMobileItemEditorOpen(false);
    setEditingItem(null);
    setItemForm(emptyItemState);
    setItemFormErrors({});
    setItemSaveError(null);
  };

  useEffect(() => {
    if (!itemForm.imageFile) {
      setImagePreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(itemForm.imageFile);
    setImagePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [itemForm.imageFile]);

  useEffect(() => {
    if (!isMobileItemEditorOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    mobileEditorCloseRef.current?.focus();
    return () => { document.body.style.overflow = previousOverflow; };
  }, [isMobileItemEditorOpen]);

  useEffect(() => {
    if (!isMobileCategoryEditorOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    mobileCategoryCloseRef.current?.focus();
    return () => { document.body.style.overflow = previousOverflow; };
  }, [isMobileCategoryEditorOpen]);

  useEffect(() => {
    if (!itemSuccess) return;
    const timer = window.setTimeout(() => setItemSuccess(null), 4000);
    return () => window.clearTimeout(timer);
  }, [itemSuccess]);

  const renderItemFields = (prefix: string, mobile: boolean) => (
    <div className="space-y-5">
      <div className="space-y-2">
        <label htmlFor={`${prefix}-name`} className="text-sm font-semibold text-slate-900">Nome do produto <span className="text-red-600">*</span></label>
        <Input
          id={`${prefix}-name`}
          value={itemForm.name}
          placeholder="Ex.: Hambúrguer da Casa"
          autoComplete="off"
          aria-invalid={Boolean(itemFormErrors.name)}
          aria-describedby={itemFormErrors.name ? `${prefix}-name-error` : undefined}
          onChange={(event) => {
            setItemForm((prev) => ({ ...prev, name: event.target.value }));
            setItemFormErrors((prev) => ({ ...prev, name: undefined }));
          }}
        />
        {itemFormErrors.name && <p id={`${prefix}-name-error`} className="text-xs font-medium text-red-600">{itemFormErrors.name}</p>}
      </div>

      <div className="space-y-2">
        <label htmlFor={`${prefix}-price`} className="text-sm font-semibold text-slate-900">Preço de venda <span className="text-red-600">*</span></label>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm font-semibold text-slate-500">R$</span>
          <Input
            id={`${prefix}-price`}
            className="pl-11"
            inputMode="decimal"
            value={itemForm.price}
            placeholder="29,90"
            aria-invalid={Boolean(itemFormErrors.price)}
            aria-describedby={itemFormErrors.price ? `${prefix}-price-error` : undefined}
            onChange={(event) => {
              setItemForm((prev) => ({ ...prev, price: event.target.value }));
              setItemFormErrors((prev) => ({ ...prev, price: undefined }));
            }}
          />
        </div>
        {itemFormErrors.price && <p id={`${prefix}-price-error`} className="text-xs font-medium text-red-600">{itemFormErrors.price}</p>}
      </div>

      <div className="space-y-2">
        <label htmlFor={`${prefix}-category`} className="text-sm font-semibold text-slate-900">Categoria</label>
        <Select id={`${prefix}-category`} value={itemForm.categoryId} onChange={(event) => setItemForm((prev) => ({ ...prev, categoryId: event.target.value }))}>
          <option value="">Sem categoria</option>
          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}{category.active ? "" : " (inativa)"}</option>)}
        </Select>
        {!categories.length && <p className="text-xs text-slate-500">Você pode cadastrar agora e criar uma categoria depois.</p>}
      </div>

      <div className="space-y-2">
        <label htmlFor={`${prefix}-image`} className="text-sm font-semibold text-slate-900">Foto do produto <span className="font-normal text-slate-500">(opcional)</span></label>
        <div className="flex items-center gap-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-3">
          <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-white text-slate-400">
            {(itemForm.imageFile ? imagePreviewUrl : resolveMediaUrl(editingItem?.image_url))
              ? <img src={(itemForm.imageFile ? imagePreviewUrl : resolveMediaUrl(editingItem?.image_url)) || undefined} alt="Prévia da foto do produto" className="h-full w-full object-cover" />
              : <ImagePlus aria-hidden="true" className="h-7 w-7" />}
          </div>
          <div className="min-w-0">
            <label htmlFor={`${prefix}-image`} className="inline-flex min-h-11 cursor-pointer items-center rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800">{imagePreviewUrl || editingItem?.image_url ? "Trocar foto" : "Adicionar foto"}</label>
            <p className="mt-1 text-xs leading-5 text-slate-500">Escolha da galeria ou tire uma foto.</p>
          </div>
          <input id={`${prefix}-image`} type="file" accept="image/*" className="sr-only" onChange={(event) => setItemForm((prev) => ({ ...prev, imageFile: event.target.files?.[0] ?? null }))} />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor={`${prefix}-description`} className="text-sm font-semibold text-slate-900">Descrição <span className="font-normal text-slate-500">(opcional)</span></label>
        <textarea id={`${prefix}-description`} rows={3} className="w-full rounded-xl border border-slate-200 px-3 py-3 text-sm" value={itemForm.description} placeholder="Conte o que vem no produto" onChange={(event) => setItemForm((prev) => ({ ...prev, description: event.target.value }))} />
      </div>

      {!mobile && <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={itemForm.active} onChange={(event) => setItemForm((prev) => ({ ...prev, active: event.target.checked }))} />Item ativo</label>}
      {editingItem && <button type="button" className="manage-modifiers-btn inline-flex min-h-11 items-center justify-center rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700" onClick={handleOpenModifiersModal}>Gerenciar adicionais</button>}
      {!editingItem && <p className="text-xs text-slate-500">Quer oferecer tamanhos ou adicionais? Cadastre o produto e depois toque em Editar.</p>}
      {itemSaveError && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{itemSaveError}</p>}
    </div>
  );

  const renderCategoryFields = (prefix: string, mobile: boolean) => (
    <div className="space-y-5">
      <div className="space-y-2">
        <label htmlFor={`${prefix}-name`} className="text-sm font-semibold text-slate-900">Nome da categoria <span className="text-red-600">*</span></label>
        <Input id={`${prefix}-name`} value={categoryName} placeholder="Ex.: Hambúrgueres" autoComplete="off" aria-invalid={Boolean(categoryError)} aria-describedby={categoryError ? `${prefix}-name-error` : undefined} onChange={(event) => { setCategoryName(event.target.value); setCategoryError(null); }} />
        {categoryError && <p id={`${prefix}-name-error`} role="alert" className="text-xs font-medium text-red-600">{categoryError}</p>}
      </div>
      <label className="flex min-h-14 items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3">
        <span className="min-w-0"><span className="block text-sm font-semibold text-slate-900">Categoria ativa</span><span className="block text-xs leading-5 text-slate-500">Aparece no cardápio para os clientes.</span></span>
        <input type="checkbox" checked={categoryActive} onChange={(event) => setCategoryActive(event.target.checked)} className="h-5 w-5 shrink-0 accent-red-600" />
      </label>
      {mobile ? (
        <details className="rounded-xl border border-slate-200 px-4 py-3" open={categoryOrderError ? true : undefined}>
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Organização do cardápio <span className="font-normal text-slate-500">(opcional)</span></summary>
          <div className="space-y-2 pt-4">
            <label htmlFor={`${prefix}-order`} className="text-sm font-medium text-slate-700">Posição da categoria</label>
            <Input id={`${prefix}-order`} type="number" min="0" step="1" inputMode="numeric" value={categoryOrder} aria-invalid={Boolean(categoryOrderError)} onChange={(event) => { setCategoryOrder(event.target.value); setCategoryOrderError(null); }} />
            <p className="text-xs leading-5 text-slate-500">Preenchida automaticamente. Um número menor aparece primeiro.</p>
            {categoryOrderError && <p role="alert" className="text-xs font-medium text-red-600">{categoryOrderError}</p>}
          </div>
        </details>
      ) : (
        <div className="space-y-2">
          <label htmlFor={`${prefix}-order`} className="text-sm font-medium text-slate-700">Posição da categoria</label>
          <Input id={`${prefix}-order`} type="number" min="0" step="1" value={categoryOrder} aria-invalid={Boolean(categoryOrderError)} onChange={(event) => { setCategoryOrder(event.target.value); setCategoryOrderError(null); }} />
          <p className="text-xs text-slate-500">Preenchida automaticamente. Um número menor aparece primeiro.</p>
          {categoryOrderError && <p role="alert" className="text-xs font-medium text-red-600">{categoryOrderError}</p>}
        </div>
      )}
    </div>
  );

  if (isSessionLoading || categoriesQuery.isLoading || itemsQuery.isLoading) {
    return <LoadingExperience label="Organizando seus produtos" />;
  }

  if (!tenantId || categoriesQuery.isError || itemsQuery.isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar o cardápio.
      </div>
    );
  }

  return (
    <Tabs defaultValue="items">
      <TabsList>
        <TabsTrigger value="items">Itens</TabsTrigger>
        <TabsTrigger value="categories">Categorias</TabsTrigger>
      </TabsList>

      <TabsContent value="categories" className="pb-24 lg:pb-0">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Card className="min-w-0">
            <CardHeader className="p-4 sm:p-6">
              <div className="flex items-center justify-between gap-3">
                <div><CardTitle>Categorias do cardápio</CardTitle><p className="mt-1 text-xs text-slate-500">{categories.length} {categories.length === 1 ? "categoria cadastrada" : "categorias cadastradas"}</p></div>
                <Button type="button" onClick={startNewCategory} className="hidden gap-2 lg:inline-flex"><Plus className="h-4 w-4" />Nova categoria</Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 p-4 pt-0 sm:p-6 sm:pt-0">
              {categories.map((category) => (
                <article
                  key={category.id}
                  className="rounded-2xl border border-slate-200 bg-white p-3"
                >
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="break-words text-sm font-semibold text-slate-950">{category.name}</h3>
                      <p className="mt-1 text-xs text-slate-500">{itemsByCategory.get(String(category.id))?.length ?? 0} {itemsByCategory.get(String(category.id))?.length === 1 ? "produto" : "produtos"} · Posição {category.sort_order}</p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${category.active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{category.active ? "Ativa" : "Inativa"}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 lg:flex lg:justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="gap-2 border-brand-200 text-brand-700 hover:bg-brand-50"
                      aria-label={`Editar categoria ${category.name}`}
                      onClick={() => handleEditCategory(category)}
                    >
                      <Pencil className="h-3.5 w-3.5" aria-hidden="true" />Editar
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="gap-2 text-red-600 hover:bg-red-50 hover:text-red-700"
                      aria-label={`Excluir categoria ${category.name}`}
                      onClick={() => handleDeleteCategory(category)}
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />Excluir
                    </Button>
                  </div>
                </article>
              ))}
              {!categories.length && (
                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-600"><p className="font-semibold text-slate-900">Organize seu cardápio</p><p className="mt-1 text-xs leading-5">Crie categorias como Hambúrgueres, Bebidas ou Sobremesas. Você poderá adicionar os produtos depois.</p></div>
              )}
            </CardContent>
          </Card>

          <Card ref={categoryEditorRef} className="hidden min-w-0 scroll-mt-24 lg:block">
            <CardHeader><CardTitle>{editingCategory ? "Editar categoria" : "Nova categoria"}</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={(event) => { event.preventDefault(); handleCategorySubmit(); }} className="space-y-6">
                {renderCategoryFields("desktop-category", false)}
                <div className="flex flex-wrap gap-2">
                  <Button type="submit" disabled={categorySaving}>{categorySaving ? "Salvando..." : editingCategory ? "Salvar categoria" : "Criar categoria"}</Button>
                  {editingCategory && <Button type="button" variant="ghost" onClick={closeCategoryEditor}>Cancelar</Button>}
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
        <Button type="button" onClick={startNewCategory} className="fixed inset-x-4 z-20 h-12 gap-2 rounded-2xl shadow-xl shadow-red-200 lg:hidden [bottom:calc(76px+env(safe-area-inset-bottom))]"><Plus className="h-5 w-5" />Nova categoria</Button>
      </TabsContent>

      {isMobileCategoryEditorOpen && (
        <div role="dialog" aria-modal="true" aria-labelledby="mobile-category-editor-title" onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); closeCategoryEditor(); } }} className="fixed inset-0 z-50 bg-white lg:hidden">
          <form className="flex h-dvh flex-col" onSubmit={(event) => { event.preventDefault(); handleCategorySubmit(); }}>
            <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 px-4 py-3">
              <div><p className="text-xs font-semibold uppercase tracking-wide text-brand-700">Cardápio</p><h2 id="mobile-category-editor-title" className="text-xl font-bold text-slate-950">{editingCategory ? "Editar categoria" : "Nova categoria"}</h2></div>
              <button ref={mobileCategoryCloseRef} type="button" onClick={closeCategoryEditor} aria-label="Fechar formulário de categoria" disabled={categorySaving} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-200 text-slate-700 disabled:opacity-50"><X className="h-5 w-5" /></button>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5">
              <p className="mb-5 text-sm leading-5 text-slate-600">Dê um nome à categoria. A posição no cardápio é preenchida automaticamente.</p>
              {renderCategoryFields("mobile-category", true)}
            </div>
            <footer className="shrink-0 border-t border-slate-200 bg-white px-4 pt-3 [padding-bottom:max(12px,env(safe-area-inset-bottom))]">
              <Button type="submit" disabled={categorySaving} className="h-12 w-full rounded-xl text-base font-bold">{categorySaving ? "Salvando..." : editingCategory ? "Salvar categoria" : "Criar categoria"}</Button>
            </footer>
          </form>
        </div>
      )}

      <TabsContent value="items" className="pb-24 lg:pb-0">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Card className="min-w-0">
            <CardHeader className="p-4 sm:p-6">
              <div className="flex items-center justify-between gap-3">
                <div><CardTitle>Produtos do cardápio</CardTitle><p className="mt-1 text-xs text-slate-500">{items.length} {items.length === 1 ? "produto cadastrado" : "produtos cadastrados"}</p></div>
                <Button type="button" onClick={() => startNewItem()} className="hidden gap-2 lg:inline-flex"><Plus className="h-4 w-4" />Novo produto</Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 p-4 pt-0 sm:p-6 sm:pt-0">
              {categories.map((category) => {
                const groupedItems = itemsByCategory.get(String(category.id)) ?? [];
                return (
                  <div key={category.id} className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="min-w-0 break-words text-sm font-semibold text-slate-700">{category.name}</h3>
                      <div className="flex items-center gap-2"><span className="rounded-lg bg-slate-100 px-2 py-1 text-[10px] text-slate-500">{groupedItems.length}</span><button type="button" onClick={() => startNewItem(String(category.id))} className="inline-flex min-h-9 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-brand-700 hover:bg-brand-50" aria-label={`Adicionar produto em ${category.name}`}><Plus className="h-4 w-4" /><span>Adicionar</span></button></div>
                    </div>
                    {groupedItems.length === 0 && (
                      <p className="rounded-xl border border-dashed border-slate-200 px-3 py-4 text-xs text-slate-500">Nenhum produto nesta categoria. Toque em Adicionar para cadastrar.</p>
                    )}
                    {groupedItems.map((item) => <MenuItemCard key={item.id} item={item} onEdit={handleEditItem} onDelete={handleDeleteItem} />)}
                  </div>
                );
              })}
              {(itemsByCategory.get("uncategorized") ?? []).length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-700">Sem categoria</h3>
                  {(itemsByCategory.get("uncategorized") ?? []).map((item) => <MenuItemCard key={item.id} item={item} onEdit={handleEditItem} onDelete={handleDeleteItem} />)}
                </div>
              )}
              {!items.length && (
                <div className="rounded-xl bg-brand-50 p-4 text-sm text-brand-800"><p className="font-semibold">Comece pelo primeiro produto</p><p className="mt-1 text-xs leading-5">Nome e preço já bastam. Foto, descrição e categoria podem ser adicionadas depois.</p></div>
              )}
            </CardContent>
          </Card>

          <Card ref={itemEditorRef} className="hidden min-w-0 scroll-mt-24 lg:block">
            <CardHeader><CardTitle>{editingItem ? "Editar produto" : "Novo produto"}</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={(event) => { event.preventDefault(); handleItemSubmit(); }} className="space-y-6">
                {renderItemFields("desktop-item", false)}
                <div className="flex flex-wrap gap-2">
                  <Button type="submit" disabled={itemSaving}>{itemSaving ? "Salvando..." : editingItem ? "Salvar produto" : "Cadastrar produto"}</Button>
                  {editingItem && <Button type="button" variant="ghost" onClick={closeItemEditor}>Cancelar</Button>}
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
        <Button type="button" onClick={() => startNewItem()} className="fixed inset-x-4 z-20 h-12 gap-2 rounded-2xl shadow-xl shadow-red-200 lg:hidden [bottom:calc(76px+env(safe-area-inset-bottom))]"><Plus className="h-5 w-5" />Novo produto</Button>
      </TabsContent>

      {itemSuccess && <div role="status" className="fixed left-4 right-4 top-20 z-40 rounded-xl bg-emerald-700 px-4 py-3 text-sm font-semibold text-white shadow-lg lg:left-auto lg:right-6">{itemSuccess}</div>}

      {isMobileItemEditorOpen && (
        <div role="dialog" aria-modal="true" aria-labelledby="mobile-item-editor-title" onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); closeItemEditor(); } }} className="fixed inset-0 z-50 bg-white lg:hidden">
          <form className="flex h-dvh flex-col" onSubmit={(event) => { event.preventDefault(); handleItemSubmit(); }}>
            <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 px-4 py-3">
              <div><p className="text-xs font-semibold uppercase tracking-wide text-brand-700">Cardápio</p><h2 id="mobile-item-editor-title" className="text-xl font-bold text-slate-950">{editingItem ? "Editar produto" : "Novo produto"}</h2></div>
              <button ref={mobileEditorCloseRef} type="button" onClick={closeItemEditor} aria-label="Fechar formulário" disabled={itemSaving} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-200 text-slate-700 disabled:opacity-50"><X className="h-5 w-5" /></button>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5">
              <p className="mb-5 text-sm leading-5 text-slate-600">Preencha nome e preço. Os outros detalhes podem ser adicionados depois.</p>
              {renderItemFields("mobile-item", true)}
            </div>
            <footer className="shrink-0 border-t border-slate-200 bg-white px-4 pt-3 [padding-bottom:max(12px,env(safe-area-inset-bottom))]">
              <Button type="submit" disabled={itemSaving} className="h-12 w-full rounded-xl text-base font-bold">{itemSaving ? "Salvando..." : editingItem ? "Salvar produto" : "Cadastrar produto"}</Button>
            </footer>
          </form>
        </div>
      )}

      {isModifiersModalOpen && (
        <div className="modifiers-modal-overlay">
          <div className="modifiers-modal-toolbar">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Gerenciar Adicionais</h2>
              {modifiersProduct && (
                <p className="text-sm text-slate-600">
                  Produto: <strong>{modifiersProduct.name}</strong>
                </p>
              )}
            </div>
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              onClick={() => setIsModifiersModalOpen(false)}
            >
              Fechar
            </button>
          </div>

          {isLoadingModifiers && <LoadingLine label="Buscando adicionais" />}
          {!isLoadingModifiers && modifiersError && (
            <p className="text-sm text-red-600">{modifiersError}</p>
          )}
          {!isLoadingModifiers && modifiersSuccess && (
            <p className="text-sm text-emerald-600">{modifiersSuccess}</p>
          )}

          {!isLoadingModifiers && modifiersProduct && (
            <div className="modifier-modal">
              <aside className="modifier-sidebar">
                <div className="modifier-sidebar-top">
                  <button
                    type="button"
                    className="modifier-action-btn"
                    onClick={() => {
                      resetCreateGroupForm();
                      setIsCreateGroupFormOpen((prev) => !prev);
                      setSelectedGroupId(null);
                    }}
                  >
                    + Criar Grupo
                  </button>
                </div>

                {isCreateGroupFormOpen && (
                  <div className="modifier-panel-card">
                    <div className="grid gap-3">
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700">Nome</label>
                        <Input value={groupName} onChange={(event) => setGroupName(event.target.value)} />
                      </div>
                      <label className="flex items-center gap-2 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          checked={groupRequired}
                          onChange={(event) => setGroupRequired(event.target.checked)}
                        />
                        Obrigatório
                      </label>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700">Mínimo</label>
                        <Input
                          type="number"
                          value={groupMinSelection}
                          onChange={(event) => setGroupMinSelection(event.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700">Máximo</label>
                        <Input
                          type="number"
                          value={groupMaxSelection}
                          onChange={(event) => setGroupMaxSelection(event.target.value)}
                        />
                      </div>
                      <Button onClick={handleCreateGroup} disabled={savingGroup || !groupName.trim()}>
                        {savingGroup ? "Salvando..." : "Salvar grupo"}
                      </Button>
                    </div>
                  </div>
                )}

                <div className="modifier-group-list">
                  {modifierGroups.map((group) => (
                    <div
                      key={group.id}
                      className={`modifier-group-item flex items-center justify-between gap-2 ${selectedGroupId === group.id ? "is-active" : ""}`}
                    >
                      <button
                        type="button"
                        className="flex-1 text-left"
                        onClick={() => handleSelectGroup(group)}
                      >
                        <span className="modifier-group-title">{group.name}</span>
                        <span className="modifier-group-meta">
                          {group.required ? "Obrigatório" : "Opcional"} • Min {group.min_selection} / Max {group.max_selection}
                        </span>
                      </button>
                      <button
                        type="button"
                        className="rounded-md p-1 text-slate-500 transition hover:bg-red-50 hover:text-red-600"
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          handleDeleteGroup(group.id, group.name);
                        }}
                        disabled={isDeletingModifier && deletingGroupId === group.id}
                        aria-label={`Excluir grupo ${group.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                  {!modifierGroups.length && (
                    <p className="text-sm text-slate-500">Nenhum grupo cadastrado.</p>
                  )}
                </div>
              </aside>

              <section className="modifier-content">
                {!selectedGroup && (
                  <div className="modifier-empty-state">
                    <p className="text-base font-medium text-slate-800">Selecione um grupo</p>
                    <p className="text-sm text-slate-500">Escolha um grupo na lateral para editar e gerenciar opções.</p>
                  </div>
                )}

                {selectedGroup && (
                  <div className="modifier-panel-card space-y-5">
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-2 md:col-span-2">
                        <label className="text-sm font-medium text-slate-700">Nome do grupo</label>
                        <Input value={groupName} onChange={(event) => setGroupName(event.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700">Mínimo</label>
                        <Input
                          type="number"
                          value={groupMinSelection}
                          onChange={(event) => setGroupMinSelection(event.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700">Máximo</label>
                        <Input
                          type="number"
                          value={groupMaxSelection}
                          onChange={(event) => setGroupMaxSelection(event.target.value)}
                        />
                      </div>
                      <label className="flex items-center gap-2 text-sm text-slate-700 md:col-span-2">
                        <input
                          type="checkbox"
                          checked={groupRequired}
                          onChange={(event) => setGroupRequired(event.target.checked)}
                        />
                        Obrigatório
                      </label>
                    </div>

                    <div>
                      <Button
                        onClick={handleSaveSelectedGroup}
                        disabled={savingGroupChanges || !groupName.trim()}
                      >
                        {savingGroupChanges ? "Salvando..." : "Salvar grupo"}
                      </Button>
                    </div>

                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-slate-900">Opções do grupo</p>
                        <span className="text-xs text-slate-500">{activeOptions.length} opções</span>
                      </div>

                      <div className="space-y-2">
                        {activeOptions.map((option) => (
                          <div
                            key={option.id}
                            className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
                          >
                            <span className="text-sm font-medium text-slate-800">{option.name}</span>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-slate-500">
                                +R$ {Number(option.price_delta || 0).toFixed(2)} • {option.is_active ? "Ativo" : "Inativo"}
                              </span>
                              <button
                                type="button"
                                className="rounded-md p-1 text-slate-500 transition hover:bg-red-50 hover:text-red-600"
                                onClick={(event) => {
                                  event.preventDefault();
                                  event.stopPropagation();
                                  handleDeleteOption(option.id, option.name);
                                }}
                                disabled={isDeletingModifier && deletingOptionId === option.id}
                                aria-label={`Excluir opção ${option.name}`}
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        ))}
                        {!activeOptions.length && (
                          <p className="text-sm text-slate-500">Nenhuma opção cadastrada.</p>
                        )}
                      </div>

                      <div className="rounded-md border border-slate-200 p-4">
                        <p className="mb-3 text-sm font-medium text-slate-900">+ Adicionar Opção</p>
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="space-y-2 md:col-span-2">
                            <label className="text-sm font-medium text-slate-700">Nome</label>
                            <Input value={optionName} onChange={(event) => setOptionName(event.target.value)} />
                          </div>
                          <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700">Preço adicional</label>
                            <Input
                              value={optionPriceDelta}
                              onChange={(event) => setOptionPriceDelta(event.target.value)}
                            />
                          </div>
                          <label className="flex items-center gap-2 text-sm text-slate-700">
                            <input
                              type="checkbox"
                              checked={optionActive}
                              onChange={(event) => setOptionActive(event.target.checked)}
                            />
                            Ativo
                          </label>
                        </div>
                        <div className="mt-4">
                          <Button
                            onClick={() => handleCreateOption(selectedGroup.id)}
                            disabled={savingOption || !optionName.trim()}
                          >
                            {savingOption ? "Salvando..." : "Salvar opção"}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      )}

      {deleteErrorToast && (
        <div className="fixed bottom-4 right-4 z-[10020] rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-lg">
          {deleteErrorToast}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(confirmDialog)}
        title={confirmDialog?.title ?? "Confirmar exclusão"}
        description={confirmDialog?.description ?? ""}
        confirmLabel={confirmDialog?.confirmLabel ?? "Excluir"}
        isLoading={isConfirmingDelete}
        onCancel={closeConfirmDialog}
        onConfirm={handleConfirmDelete}
      />
    </Tabs>
  );
}
