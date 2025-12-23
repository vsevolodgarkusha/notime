/// <reference types="vite/client" />

interface Window {
  Telegram?: {
    WebApp?: {
      ready: () => void;
      expand: () => void;
      initData?: string;
      initDataUnsafe?: {
        user?: {
          id: number;
        };
      };
    };
  };
}
