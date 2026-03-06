import { useDriverStatusContext } from "../context/DriverStatusContext";

export function useDriverStatus() {
  return useDriverStatusContext();
}
