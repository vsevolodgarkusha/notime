/// <reference types="vite/client" />

interface Window {
  Telegram?: {
    WebApp?: {
      ready: () => void;
      initDataUnsafe?: {
        user?: {
          id: number;
        };
      };
    };
  };
}
