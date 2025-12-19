/// <reference types="vite/client" />

interface Window {
  Telegram?: {
    WebApp?: {
      ready: () => void;
      expand: () => void;
      initDataUnsafe?: {
        user?: {
          id: number;
        };
      };
    };
  };
}
