export const formatCurrency = (value: number) =>
  new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);

export const formatCurrencyFromCents = (valueInCents: number) => formatCurrency(valueInCents / 100);
