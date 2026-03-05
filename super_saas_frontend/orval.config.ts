import { defineConfig } from "orval";

export default defineConfig({
  deliveryApi: {
    input: "https://service-delivery-backend-production.up.railway.app/openapi.json",
    output: {
      target: "./src/api/generated.ts",
      client: "axios",
      mode: "single",
    },
  },
});
