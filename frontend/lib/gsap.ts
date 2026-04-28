"use client";

import gsap from "gsap";
import { useGSAP } from "@gsap/react";

if (typeof gsap.registerPlugin === "function") {
  gsap.registerPlugin(useGSAP);
}

export { gsap, useGSAP };
