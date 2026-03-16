let googleMapsPromise: Promise<any> | null = null;

export function loadGoogleMaps(apiKey: string) {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Google Maps can only be loaded in the browser"));
  }

  if (!googleMapsPromise) {
    googleMapsPromise = new Promise((resolve, reject) => {
      const browserWindow = window as Window & { google?: any };

      if (browserWindow.google?.maps) {
        resolve(browserWindow.google);
        return;
      }

      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places`;
      script.async = true;
      script.defer = true;

      script.onload = () => resolve(browserWindow.google);
      script.onerror = reject;

      document.head.appendChild(script);
    });
  }

  return googleMapsPromise;
}
