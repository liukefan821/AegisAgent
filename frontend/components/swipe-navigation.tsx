"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useRef } from "react";

const ROUTES = ["/", "/vault", "/agents", "/activity"] as const;
const SWIPE_THRESHOLD = 70;
const VERTICAL_TOLERANCE = 45;
const MOBILE_QUERY = "(max-width: 767px)";

const INTERACTIVE_SELECTOR = [
  "a",
  "button",
  "input",
  "textarea",
  "select",
  "[role='button']",
  "[data-no-swipe]",
].join(",");

type TouchPoint = {
  x: number;
  y: number;
  target: EventTarget | null;
};

export function SwipeNavigation({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const startPoint = useRef<TouchPoint | null>(null);

  const routeIndex = ROUTES.findIndex((route) => route === pathname);

  return (
    <div
      className="h-full"
      onTouchStart={(event) => {
        const target = event.target;
        if (
          target instanceof Element &&
          target.closest(INTERACTIVE_SELECTOR)
        ) {
          startPoint.current = null;
          return;
        }

        const touch = event.touches[0];
        startPoint.current = {
          x: touch.clientX,
          y: touch.clientY,
          target,
        };
      }}
      onTouchEnd={(event) => {
        const start = startPoint.current;
        startPoint.current = null;

        if (
          !start ||
          routeIndex === -1 ||
          !window.matchMedia(MOBILE_QUERY).matches
        ) {
          return;
        }

        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - start.x;
        const deltaY = touch.clientY - start.y;

        if (
          Math.abs(deltaX) < SWIPE_THRESHOLD ||
          Math.abs(deltaY) > VERTICAL_TOLERANCE
        ) {
          return;
        }

        const nextIndex = deltaX < 0 ? routeIndex + 1 : routeIndex - 1;
        const nextRoute = ROUTES[nextIndex];

        if (nextRoute) {
          router.push(nextRoute);
        }
      }}
    >
      {children}
    </div>
  );
}
