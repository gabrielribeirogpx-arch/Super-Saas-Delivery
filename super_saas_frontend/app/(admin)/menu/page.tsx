"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

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
  const [editingCategory, setEditingCategory] = useState<MenuCategory | null>(null);
  const [categoryName, setCategoryName] = useState("");
  const [categoryOrder, setCategoryOrder] = useState("0");
  const [categoryActive, setCategoryActive] = useState(true);
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [itemForm, setItemForm] = useState<MenuItemFormState>(emptyItemState);

  const categoriesQuery = useQuery({
    queryKey: ["menu-categories"],
    queryFn: () =>
      api.get<MenuCategory[]>(`/api/admin/menu/categories`),
  });

  const itemsQuery = useQuery({
    queryKey: ["menu-items"],
    queryFn: () => api.get<MenuItem[]>(`/api/admin/menu/items`),
  });

  const createCategory = useMutation({
    mutationFn: (payload: { name: string; sort_order: number; active: boolean }) =>
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
    const payload = {
      name: categoryName,
      sort_order: Number(categoryOrder || 0),
      active: categoryActive,
    };
    if (editingCategory) {
      updateCategory.mutate({ id: editingCategory.id, ...payload });
    } else {
      createCategory.mutate(payload);
    }
  };

  const handleEditCategory = (category: MenuCategory) => {
    setEditingCategory(category);
    setCategoryName(category.name);
    setCategoryOrder(String(category.sort_order));
    setCategoryActive(category.active);
  };

  const handleItemSubmit = () => {
    const formData = new FormData();    formData.append("name", itemForm.name);
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
                      variant="ghost"
                      size="sm"
                      onClick={() => deactivateCategory.mutate(category.id)}
                    >
                      Desativar
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
                          {item.image_url && (
                            <img
                              src={item.image_url}
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
                            variant="ghost"
                            size="sm"
                            onClick={() => deactivateItem.mutate(item.id)}
                          >
                            Desativar
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
                        {item.image_url && (
                          <img
                            src={item.image_url}
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
                          variant="ghost"
                          size="sm"
                          onClick={() => deactivateItem.mutate(item.id)}
                        >
                          Desativar
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
    </Tabs>
  );
}
