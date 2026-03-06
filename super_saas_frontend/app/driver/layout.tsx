import { DriverStatusProvider } from "../../context/DriverStatusContext";

export default function DriverAreaLayout({ children }: { children: React.ReactNode }) {
  return <DriverStatusProvider>{children}</DriverStatusProvider>;
}
