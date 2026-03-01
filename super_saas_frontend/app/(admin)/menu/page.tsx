"use client";

import { useEffect, useMemo, useState } from "react";
import { Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSession } from "@/hooks/use-session";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/media";

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

interface ConfirmDeleteState {
  type: "group" | "option";
  id: number;
  name: string;
}

interface MenuItemFormState {
  name: string;
  description: string;
  price: string;
  categoryId: string;
  active: boolean;
  imageFile: File | null;
}

const emptyItemState: MenuItemFormState = {
  name: "",
  description: "",
  price: "",
  categoryId: "",
  active: true,
  imageFile: null,
};

export default function MenuPage() {
  const queryClient = useQueryClient();
  const { data: session, isLoading: isSessionLoading } = useSession();
  const tenantId = session?.tenant_id;
  const [editingCategory, setEditingCategory] = useState<MenuCategory | null>(null);
  const [categoryName, setCategoryName] = useState("");
  const [categoryOrder, setCategoryOrder] = useState("0");
  const [categoryActive, setCategoryActive] = useState(true);
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [itemForm, setItemForm] = useState<MenuItemFormState>(emptyItemState);
  const [isModifiersModalOpen, setIsModifiersModalOpen] = useState(false);
  const [modifiersProduct, setModifiersProduct] = useState<MenuItem | null>(null);
  const [isLoadingModifiers, setIsLoadingModifiers] = useState(false);
  const [modifiersError, setModifiersError] = useState<string | null>(null);
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
  const [confirmDeleteState, setConfirmDeleteState] = useState<ConfirmDeleteState | null>(null);

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
    },
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
    },
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
    },
  });

  const updateItem = useMutation({
    mutationFn: (payload: { id: number; formData: FormData }) =>
      api.put<MenuItem>(`/api/admin/menu/items/${payload.id}`, payload.formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
      setEditingItem(null);
      setItemForm(emptyItemState);
    },
  });

  const deactivateItem = useMutation({
    mutationFn: (itemId: number) =>
      api.delete<MenuItem>(`/api/admin/menu/items/${itemId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
    },
  });

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

    const categoryPayload = {
      name: categoryName,
      sort_order: Number(categoryOrder || 0),
      active: categoryActive,
    };
    if (editingCategory) {
      updateCategory.mutate({ id: editingCategory.id, ...categoryPayload });
    } else {
      createCategory.mutate({ tenant_id: tenantId, ...categoryPayload });
    }
  };

  const handleEditCategory = (category: MenuCategory) => {
    setEditingCategory(category);
    setCategoryName(category.name);
    setCategoryOrder(String(category.sort_order));
    setCategoryActive(category.active);
  };

  const handleDeleteCategory = (category: MenuCategory) => {
    const shouldDelete = window.confirm(
      `Deseja realmente excluir a categoria \"${category.name}\"?`
    );
    if (!shouldDelete) {
      return;
    }

    deactivateCategory.mutate(category.id);
  };

  const handleItemSubmit = () => {
    if (!tenantId) {
      return;
    }

    const formData = new FormData();
    formData.append("name", itemForm.name);
    formData.append("tenant_id", String(tenantId));
    formData.append("description", itemForm.description);
    formData.append(
      "price_cents",
      String(Math.round(Number(itemForm.price.replace(",", ".")) * 100) || 0)
    );
    if (itemForm.categoryId) {
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

  const handleEditItem = (item: MenuItem) => {
    setEditingItem(item);
    setItemForm({
      name: item.name,
      description: item.description ?? "",
      price: (item.price_cents / 100).toFixed(2),
      categoryId: item.category_id ? String(item.category_id) : "",
      active: item.active,
      imageFile: null,
    });
  };

  const handleDeleteItem = (item: MenuItem) => {
    const shouldDelete = window.confirm(
      `Deseja realmente excluir o item \"${item.name}\"?`
    );
    if (!shouldDelete) {
      return;
    }

    deactivateItem.mutate(item.id);
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

  const handleRequestDeleteGroup = (group: ModifierGroup) => {
    setConfirmDeleteState({ type: "group", id: group.id, name: group.name });
  };

  const handleRequestDeleteOption = (_groupId: number, option: ModifierOption) => {
    setConfirmDeleteState({ type: "option", id: option.id, name: option.name });
  };

  const handleConfirmDeleteModifier = async () => {
    if (!confirmDeleteState || !modifiersProduct) {
      return;
    }

    setIsDeletingModifier(true);
    setModifiersError(null);
    try {
      if (confirmDeleteState.type === "group") {
        await api.delete(`/api/admin/modifier-groups/${confirmDeleteState.id}`);
      } else {
        await api.delete(`/api/admin/modifier-options/${confirmDeleteState.id}`);
      }
      const refreshedProduct = await loadProductModifiers(modifiersProduct.id);
      if (confirmDeleteState.type === "group" && selectedGroupId === confirmDeleteState.id) {
        const firstGroupId = refreshedProduct?.modifier_groups?.[0]?.id ?? null;
        setSelectedGroupId(firstGroupId);
      }
      queryClient.invalidateQueries({ queryKey: ["menu-items"] });
      setConfirmDeleteState(null);
    } catch {
      setModifiersError("Não foi possível excluir. Tente novamente.");
    } finally {
      setIsDeletingModifier(false);
    }
  };

  const modifierGroups = modifiersProduct?.modifier_groups ?? [];
  const selectedGroup = modifierGroups.find((group) => group.id === selectedGroupId) ?? null;
  const activeOptions = selectedGroup?.options.filter((option) => option.is_active) ?? [];

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

  if (isSessionLoading || categoriesQuery.isLoading || itemsQuery.isLoading) {
    return <p className="text-sm text-slate-500">Carregando cardápio...</p>;
  }

  if (!tenantId || categoriesQuery.isError || itemsQuery.isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Não foi possível carregar o cardápio.
      </div>
    );
  }

  return (
    <Tabs defaultValue="categories">
      <TabsList>
        <TabsTrigger value="categories">Categorias</TabsTrigger>
        <TabsTrigger value="items">Itens</TabsTrigger>
      </TabsList>

      <TabsContent value="categories">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>Categorias cadastradas</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {categories.map((category) => (
                <div
                  key={category.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-3"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-900">{category.name}</p>
                    <p className="text-xs text-slate-500">
                      Ordem: {category.sort_order} •{" "}
                      {category.active ? "Ativa" : "Inativa"}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleEditCategory(category)}
                    >
                      Editar
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteCategory(category)}
                    >
                      Excluir
                    </Button>
                  </div>
                </div>
              ))}
              {!categories.length && (
                <p className="text-sm text-slate-500">Nenhuma categoria cadastrada.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>
                {editingCategory ? "Editar categoria" : "Nova categoria"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Nome</label>
                <Input
                  value={categoryName}
                  onChange={(event) => setCategoryName(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Ordem</label>
                <Input
                  type="number"
                  value={categoryOrder}
                  onChange={(event) => setCategoryOrder(event.target.value)}
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={categoryActive}
                  onChange={(event) => setCategoryActive(event.target.checked)}
                />
                Categoria ativa
              </label>
              <div className="flex gap-2">
                <Button onClick={handleCategorySubmit}>
                  {editingCategory ? "Salvar" : "Criar"}
                </Button>
                {editingCategory && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEditingCategory(null);
                      setCategoryName("");
                      setCategoryOrder("0");
                      setCategoryActive(true);
                    }}
                  >
                    Cancelar
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="items">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>Itens por categoria</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {categories.map((category) => {
                const groupedItems = itemsByCategory.get(String(category.id)) ?? [];
                return (
                  <div key={category.id} className="space-y-3">
                    <h3 className="text-sm font-semibold text-slate-700">
                      {category.name}
                    </h3>
                    {groupedItems.length === 0 && (
                      <p className="text-xs text-slate-500">
                        Nenhum item nesta categoria.
                      </p>
                    )}
                    {groupedItems.map((item) => (
                      <div
                        key={item.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-3"
                      >
                        <div className="flex items-center gap-3">
                          {resolveMediaUrl(item.image_url) && (
                            <img
                              src={resolveMediaUrl(item.image_url) ?? undefined}
                              alt={item.name}
                              className="h-12 w-12 rounded-md object-cover"
                            />
                          )}
                          <div>
                            <p className="text-sm font-medium text-slate-900">{item.name}</p>
                            {item.description && (
                              <p className="text-xs text-slate-500">{item.description}</p>
                            )}
                            <p className="text-xs text-slate-500">
                              R$ {(item.price_cents / 100).toFixed(2)} •{" "}
                              {item.active ? "Ativo" : "Inativo"}
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEditItem(item)}
                          >
                            Editar
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDeleteItem(item)}
                          >
                            Excluir
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                );
              })}
              {(itemsByCategory.get("uncategorized") ?? []).length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-700">Sem categoria</h3>
                  {(itemsByCategory.get("uncategorized") ?? []).map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-3"
                    >
                      <div className="flex items-center gap-3">
                        {resolveMediaUrl(item.image_url) && (
                          <img
                            src={resolveMediaUrl(item.image_url) ?? undefined}
                            alt={item.name}
                            className="h-12 w-12 rounded-md object-cover"
                          />
                        )}
                        <div>
                          <p className="text-sm font-medium text-slate-900">{item.name}</p>
                          {item.description && (
                            <p className="text-xs text-slate-500">{item.description}</p>
                          )}
                          <p className="text-xs text-slate-500">
                            R$ {(item.price_cents / 100).toFixed(2)} •{" "}
                            {item.active ? "Ativo" : "Inativo"}
                          </p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleEditItem(item)}
                        >
                          Editar
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDeleteItem(item)}
                        >
                          Excluir
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {!items.length && (
                <p className="text-sm text-slate-500">Nenhum item cadastrado.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{editingItem ? "Editar item" : "Novo item"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Nome</label>
                <Input
                  value={itemForm.name}
                  onChange={(event) =>
                    setItemForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Descrição</label>
                <textarea
                  className="min-h-[80px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                  value={itemForm.description}
                  onChange={(event) =>
                    setItemForm((prev) => ({ ...prev, description: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Preço (R$)</label>
                <Input
                  value={itemForm.price}
                  onChange={(event) =>
                    setItemForm((prev) => ({ ...prev, price: event.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Categoria</label>
                <Select
                  value={itemForm.categoryId}
                  onChange={(event) =>
                    setItemForm((prev) => ({ ...prev, categoryId: event.target.value }))
                  }
                >
                  <option value="">Sem categoria</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </Select>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={itemForm.active}
                  onChange={(event) =>
                    setItemForm((prev) => ({ ...prev, active: event.target.checked }))
                  }
                />
                Item ativo
              </label>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Foto</label>
                <Input
                  type="file"
                  accept="image/*"
                  onChange={(event) =>
                    setItemForm((prev) => ({
                      ...prev,
                      imageFile: event.target.files?.[0] ?? null,
                    }))
                  }
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleItemSubmit}>
                  {editingItem ? "Salvar" : "Criar"}
                </Button>
                {editingItem && (
                  <button
                    type="button"
                    className="manage-modifiers-btn inline-flex items-center justify-center rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    onClick={handleOpenModifiersModal}
                  >
                    Gerenciar Adicionais
                  </button>
                )}
                {editingItem && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEditingItem(null);
                      setItemForm(emptyItemState);
                    }}
                  >
                    Cancelar
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

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

          {isLoadingModifiers && <p className="text-sm text-slate-500">Carregando...</p>}
          {!isLoadingModifiers && modifiersError && (
            <p className="text-sm text-red-600">{modifiersError}</p>
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
                        onClick={() => handleRequestDeleteGroup(group)}
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
                                onClick={() => handleRequestDeleteOption(selectedGroup.id, option)}
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
      {confirmDeleteState && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4">
          <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl">
            <h4 className="text-base font-semibold text-slate-900">Confirmar exclusão</h4>
            <p className="mt-2 text-sm text-slate-600">
              {confirmDeleteState.type === "group"
                ? `Deseja excluir o grupo "${confirmDeleteState.name}" e desativar suas opções?`
                : `Deseja excluir a opção "${confirmDeleteState.name}"?`}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Essa ação mantém o histórico dos pedidos e remove o adicional apenas das novas vendas.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setConfirmDeleteState(null)}
                disabled={isDeletingModifier}
              >
                Cancelar
              </Button>
              <Button
                variant="destructive"
                onClick={handleConfirmDeleteModifier}
                disabled={isDeletingModifier}
              >
                {isDeletingModifier ? "Excluindo..." : "Excluir"}
              </Button>
            </div>
          </div>
        </div>
      )}

    </Tabs>
  );
}
