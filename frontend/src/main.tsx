import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { logoUrl } from "./branding";
import "./index.css";

const fav = document.createElement("link");
fav.rel = "icon";
fav.type = "image/png";
fav.href = logoUrl;
document.head.appendChild(fav);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
